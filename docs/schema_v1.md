# schema_v1.md

## Field Definitions

### JSONSchema v1.0

```
{
  "type": "object",
  "properties": {
    "doc_id": {"type": "string", "description": "SHA256 hash of canonical_url"},
    "canonical_url": {"type": "string", "format": "uri", "description": "Canonical URL for the document"},
    "entity_type": {"type": "string", "description": "Entity type (event, staff, program, other)"},
    "text": {"type": "string", "description": "Cleaned, readable text extracted from the page"},
    "raw": {"type": "object", "description": "Original raw page JSON as ingested from S3"}
  },
  "required": ["doc_id", "canonical_url", "entity_type", "text", "raw"]
}
```

## Examples

```
{
  "doc_id": "31177467fe0aeea47859b081ef1c533711bcfeb79e91a96a2a6a6f65a5deceed",
  "canonical_url": "https://dmeacademy.com/news-updates/",
  "entity_type": "other",
  "text": "DME Academy News and Updates... (cleaned, readable text)",
  "raw": {
    "url": "https://dmeacademy.com/news-updates/",
    "html": "<html>...</html>",
    "scraped_at": "2024-06-01T12:00:00Z",
    "etag": "abc123",
    "checksum": "def456"
  }
}
``` 