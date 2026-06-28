---
name: api-doc-writing
description: Write clear and consistent API documentation following team standards. Use when creating or editing REST API reference docs.
license: MIT
metadata:
  audience: developers
  domain: technical-writing
---

# API Documentation Writing Skill

Guidelines for writing REST API reference documentation.

## When to use

Use this skill when:

- Writing new API endpoint documentation
- Editing existing API reference pages
- Reviewing API docs for consistency

## Document structure

### Standard sections

1. **Overview** - Brief description of the endpoint purpose
2. **Request** - HTTP method, URL, headers, and body parameters
3. **Response** - Status codes and response body schema
4. **Examples** - Request/response examples with curl commands
5. **Errors** - Common error codes and troubleshooting

## Formatting rules

### Endpoint naming

- Use lowercase with hyphens for URL paths
- Use nouns for resources, not verbs
- Version prefix required: `/v1/users`, not `/users`

### Parameter tables

- Every parameter must have: name, type, required, description
- Use `string`, `integer`, `boolean`, `array`, `object` for types
- Mark optional parameters explicitly

### Examples section

- Include at least one success and one error example
- Use curl commands for request examples
- Show full JSON response bodies

## Best practices

- Start each endpoint doc with a one-sentence summary
- Document rate limits and authentication requirements upfront
- Keep examples realistic but anonymized (no real API keys)
- Link to related endpoints for discoverability

## Example

Request:

```bash
curl -X GET "https://api.example.com/v1/users/123" \
  -H "Authorization: Bearer <token>"
```

Response:

```json
{
  "id": 123,
  "name": "Alice",
  "email": "alice@example.com"
}
```
