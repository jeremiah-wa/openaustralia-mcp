# Test only through the MCP tool call

Tests could cover the API clients and result shaping directly. Instead they call tools through an in-memory MCP client, and nothing below the tool call is tested on its own, because that keeps the internals free to change when the tools are reworked around tasks. The eval's own logic, such as the graders and the case format, is tested directly, because it isn't part of the server.
