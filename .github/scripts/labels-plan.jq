# What to change on GitHub so its labels match .github/labels.yml. Takes $file (the labels in labels.yml) and
# $github (the labels on GitHub, as `gh label list --json name,color,description` gives them). Returns a list of
# changes, each with an `action`: rename, update, create or delete.
#
# Names are compared ignoring case, as GitHub compares them. A label on GitHub that's in `renamed_from` is renamed,
# which keeps it on its issues, and one that's in neither is deleted.

def key: ascii_downcase;

($github | map({key: (.name | key), value: .}) | from_entries) as $existing
| [
    $file[] as $label
    | ($label.name | key) as $name
    | if $existing[$name] then
        $existing[$name] as $old
        # Includes a change of case only, such as Bug to bug.
        | if $old.name != $label.name or ($old.color | key) != ($label.color | key) or $old.description != $label.description
          then {action: "update", name: $old.name, new_name: $label.name, color: $label.color, description: $label.description}
          else empty
          end
      else
        ([($label.renamed_from // [])[] | key | select($existing[.])] | first) as $from
        | if $from
          then {action: "rename", name: $existing[$from].name, new_name: $label.name, color: $label.color, description: $label.description}
          else {action: "create", name: $label.name, color: $label.color, description: $label.description}
          end
      end
  ] as $changes
| ($file | map(.name | key)) as $listed
| ($changes | map(select(.action == "rename") | .name | key)) as $renamed
| $changes + [
    $github[]
    | (.name | key) as $name
    | select(($name | IN($listed[]) | not) and ($name | IN($renamed[]) | not))
    | {action: "delete", name}
  ]
