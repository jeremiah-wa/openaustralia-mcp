# stdio first, with a transport-agnostic core

A claude.ai connector needs a remote HTTP server, but local use needs no hosting, so the first release runs over stdio only. The server core knows nothing about its transport, so HTTP can be added later without a refactor: only the entry point and how the config is supplied change.
