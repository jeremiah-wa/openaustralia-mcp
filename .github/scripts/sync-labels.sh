#!/usr/bin/env bash
# Makes the repository's labels match .github/labels.yml. Run from the repository root by the Labels workflow.
#
#   sync-labels.sh plan    check the file, and print what would change
#   sync-labels.sh apply   the same, then make the changes
#
# Either way it fails, before changing anything, if the file is malformed or a label to delete is still on an issue
# or a pull request. Deleting a label takes it off everything that has it, and recreating it doesn't put it back.
set -euo pipefail

mode=${1:?usage: sync-labels.sh plan|apply}
labels_file=.github/labels.yml
here=$(dirname "$0")

file=$(yq -o=json '.' "$labels_file")

# GitHub allows descriptions up to 100 characters, and matches names ignoring case. A colour must be quoted when it's
# all digits, or YAML reads it as a number. An old name in renamed_from can't also be a label or listed twice.
if ! jq -e '
  all(.[];
    (.name | type == "string" and length > 0)
    and (.color | type == "string" and test("^[0-9a-fA-F]{6}$"))
    and (.description | type == "string" and length <= 100)
    and ((.renamed_from // []) | type == "array" and all(.[]; type == "string" and length > 0)))
  and ([.[] | .name, (.renamed_from // [])[]] | map(ascii_downcase) | length == (unique | length))
' <<< "$file" > /dev/null; then
  echo "::error file=$labels_file::Every label needs a name, a six-digit hex colour and a description of up to 100 characters, and no name, current or in renamed_from, can repeat."
  exit 1
fi

github=$(gh label list --limit 1000 --json name,color,description)
plan=$(jq -n --argjson file "$file" --argjson github "$github" -f "$here/labels-plan.jq")

# The labels to delete that are still on an issue or a pull request, as a JSON list.
in_use='[]'
while IFS= read -r name; do
  issue=$(gh issue list --label "$name" --state all --limit 1 --json number --jq '.[].number')
  pull=$(gh pr list --label "$name" --state all --limit 1 --json number --jq '.[].number')
  if [ -n "$issue$pull" ]; then
    in_use=$(jq -c --arg name "$name" '. + [$name]' <<< "$in_use")
  fi
done < <(jq -r '.[] | select(.action == "delete") | .name' <<< "$plan")

report=$(jq -r --argjson in_use "$in_use" '
  if length == 0 then "The labels on GitHub already match labels.yml."
  else .[] | if .action == "rename" then "- rename `\(.name)` to `\(.new_name)`"
    elif .action == "update" then "- update `\(.new_name)`"
    elif .action == "create" then "- create `\(.name)`"
    elif (.name | IN($in_use[])) then "- delete `\(.name)`: **refused, it is still on an issue or a pull request**"
    else "- delete `\(.name)`"
    end
  end
' <<< "$plan")
echo "$report"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  printf '## Labels\n\n%s\n' "$report" >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$(jq length <<< "$in_use")" -gt 0 ]; then
  echo "::error file=$labels_file::Won't delete a label that's in use: $(jq -r 'join(", ")' <<< "$in_use"). Take it off those issues and pull requests first, add it back to labels.yml, or list its old name in another label's renamed_from."
  exit 1
fi

if [ "$mode" = apply ]; then
  # In the plan's order: the labels in labels.yml, in file order, then the deletions.
  jq -c '.[]' <<< "$plan" | while IFS= read -r change; do
    action=$(jq -r .action <<< "$change")
    name=$(jq -r .name <<< "$change")
    case "$action" in
      rename | update)
        gh label edit "$name" --name "$(jq -r .new_name <<< "$change")" \
          --color "$(jq -r .color <<< "$change")" --description "$(jq -r .description <<< "$change")" ;;
      create)
        gh label create "$name" --color "$(jq -r .color <<< "$change")" --description "$(jq -r .description <<< "$change")" ;;
      delete)
        gh label delete "$name" --yes ;;
    esac
  done
fi
