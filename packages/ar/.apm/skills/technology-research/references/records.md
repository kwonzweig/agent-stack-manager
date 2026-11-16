# Research records

Keep `state.json` in the company's durable research directory. The maps use stable
source, item, and run IDs. An empty workspace starts with empty maps, the current
brief/source-list versions, and `schema_version: 1`.

The schema below is the format for that file. Extract the JSON block when using a
JSON Schema validator.

Unknown historical values stay null; explain the missing information in the source's
pending reason, item's unknowns, or run report. New reports receive an ID before any
delivery attempt. A historical delivered report may have an unknown ID; that does
not authorize sending it again.

Timestamps use ISO 8601 with an offset. Windows are inclusive start and exclusive end.
A cursor is the next unread page; a completed window excludes gaps. A source's
`last_success` is its last successful page, not proof of a complete scan.

Counts describe this attempt: inspected includes cached items considered; new,
changed, unchanged, and excluded partition inspected items. Duplicate counts can
overlap those groups because distinct articles may repeat one origin.

Source IDs in items, gaps, and checkpoints must exist in `sources`. Item and run brief
versions refer to the brief used for their assessment. Schema validation checks the
shape; also check these references, window order, and that completed coverage does
not cross an unread gap before saving.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Technology research state",
  "type": "object",
  "required": ["schema_version","brief_version","sources_version","sources","items","runs"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const":1},
    "brief_version": {"type":["string","null"],"minLength":1},
    "sources_version": {"type":["string","null"],"minLength":1},
    "sources": {"type":"object","propertyNames":{"minLength":1},"additionalProperties":{"$ref":"#/$defs/source"}},
    "items": {"type":"object","propertyNames":{"minLength":1},"additionalProperties":{"$ref":"#/$defs/item"}},
    "runs": {"type":"object","propertyNames":{"minLength":1},"additionalProperties":{"$ref":"#/$defs/run"}}
  },
  "$defs": {
    "checkpoint": {
      "type": "object",
      "required": ["run_id","requested_window","completed_window","timezone","cursor","last_seen_ids","validator","last_attempt","last_success","pending_reason"],
      "additionalProperties": false,
      "properties": {
        "run_id": {"type":["string","null"]},
        "requested_window": {"type":["array","null"],"items":{"type":["string","null"],"format":"date-time"},"minItems":2,"maxItems":2},
        "completed_window": {"type":["array","null"],"items":{"type":["string","null"],"format":"date-time"},"minItems":2,"maxItems":2},
        "timezone": {"type":["string","null"],"minLength":1},
        "cursor": {"type":["string","null"]},
        "last_seen_ids": {"type":["array","null"],"items":{"type":"string","minLength":1},"uniqueItems":true},
        "validator": {"type":["object","null"],"additionalProperties":false,"properties":{"etag":{"type":["string","null"]},"last_modified":{"type":["string","null"]},"content_hash":{"type":["string","null"]}}},
        "last_attempt": {"type":["string","null"],"format":"date-time"},
        "last_success": {"type":["string","null"],"format":"date-time"},
        "pending_reason": {"type":["string","null"]}
      }
    },
    "source": {
      "type": "object",
      "required": ["url","topic","route","account","query","authorized_scope","recheck_after","checkpoint"],
      "additionalProperties": false,
      "properties": {
        "url": {"type":["string","null"],"format":"uri"},
        "topic": {"type":"string","minLength":1},
        "route": {"enum":["feed","api","browser"]},
        "account": {"type":["string","null"]},
        "query": {"type":["string","null"]},
        "authorized_scope": {"type":"string","minLength":1},
        "recheck_after": {"type":["string","null"],"format":"date-time"},
        "checkpoint": {"$ref":"#/$defs/checkpoint"}
      }
    },
    "item": {
      "type": "object",
      "required": ["source_id","provider_id","url","aliases","published_at","updated_at","read_at","revision","fingerprint","read_scope","origins","claim","brief_version","relevance","evidence","recommendation","reason","unknowns"],
      "additionalProperties": false,
      "properties": {
        "source_id": {"type":"string","minLength":1},
        "provider_id": {"type":["string","null"]},
        "url": {"type":"string","format":"uri"},
        "aliases": {"type":"array","items":{"type":"string","minLength":1},"uniqueItems":true},
        "published_at": {"type":["string","null"],"format":"date-time"},
        "updated_at": {"type":["string","null"],"format":"date-time"},
        "read_at": {"type":["string","null"],"format":"date-time"},
        "revision": {"type":["string","null"]},
        "fingerprint": {"type":["string","null"]},
        "read_scope": {"type":"string","minLength":1},
        "origins": {"type":"array","items":{"type":"string","minLength":1},"uniqueItems":true},
        "claim": {"type":"string","minLength":1},
        "brief_version": {"type":["string","null"],"minLength":1},
        "relevance": {"type":"string","minLength":1},
        "evidence": {"type":"string","minLength":1},
        "recommendation": {"enum":["investigate","trial","watch","dismiss"]},
        "reason": {"type":"string","minLength":1},
        "unknowns": {"type":"array","items":{"type":"string","minLength":1},"uniqueItems":true}
      }
    },
    "gap": {
      "type": "object",
      "required": ["source_id","window","locator","reason"],
      "additionalProperties": false,
      "properties": {
        "source_id": {"type":"string","minLength":1},
        "window": {"type":["array","null"],"items":{"type":["string","null"],"format":"date-time"},"minItems":2,"maxItems":2},
        "locator": {"type":["string","null"]},
        "reason": {"type":"string","minLength":1}
      }
    },
    "run": {
      "type": "object",
      "required": ["brief_version","sources_version","status","checkpoints_before","checkpoints_after","counts","gaps","effort_stopped","report_id","delivery"],
      "additionalProperties": false,
      "properties": {
        "brief_version": {"type":["string","null"],"minLength":1},
        "sources_version": {"type":["string","null"],"minLength":1},
        "status": {"enum":["complete","partial","failed"]},
        "checkpoints_before": {"type":["object","null"],"propertyNames":{"minLength":1},"additionalProperties":{"$ref":"#/$defs/checkpoint"}},
        "checkpoints_after": {"type":"object","propertyNames":{"minLength":1},"additionalProperties":{"$ref":"#/$defs/checkpoint"}},
        "counts": {"type":"object","required":["inspected","new","changed","unchanged","duplicate","excluded"],"additionalProperties":false,"properties":{"inspected":{"type":["integer","null"],"minimum":0},"new":{"type":["integer","null"],"minimum":0},"changed":{"type":["integer","null"],"minimum":0},"unchanged":{"type":["integer","null"],"minimum":0},"duplicate":{"type":["integer","null"],"minimum":0},"excluded":{"type":["integer","null"],"minimum":0}}},
        "gaps": {"type":"array","items":{"$ref":"#/$defs/gap"}},
        "effort_stopped": {"type":["boolean","null"]},
        "report_id": {"type":["string","null"]},
        "delivery": {"enum":["none","pending","delivered"]}
      },
      "allOf": [{"if":{"properties":{"status":{"const":"complete"}}},"then":{"properties":{"gaps":{"maxItems":0},"effort_stopped":{"const":false}}}},{"if":{"properties":{"delivery":{"const":"pending"}}},"then":{"properties":{"report_id":{"type":"string","minLength":1}}}}]
    }
  }
}
```
