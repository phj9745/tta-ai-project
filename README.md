# tta-ai-project
AI-ON 업무혁신 공모전

## Attachment descriptor template placeholders
The admin prompts page lets you customize how attachment descriptions are rendered using a template string. The following placeholder keys are supported in the template:

- `{{index}}`: 1-based position of the attachment in the list that will be shown to the model.
- `{{descriptor}}`: Human-readable title generated from the attachment metadata (label, filename, and file extension).
- `{{label}}`: Friendly name entered for the attachment; falls back to the uploaded filename when no label is provided.
- `{{description}}`: Longer free-text description supplied with the attachment metadata.
- `{{extension}}`: File extension (for example, `pdf`, `pptx`, or `jpg`).
- `{{doc_id}}`: Identifier of a required document when one is available; otherwise this placeholder resolves to an empty string.
- `{{notes}}`: Any additional notes that were stored with the attachment.
- `{{source_path}}`: Original source path stored in the attachment metadata.

When you upload multiple files the admin preview also shows the `{{context_summary}}` placeholder. It expands to a comma-separated list of the attachment labels (falling back to each file's descriptor when no label is provided). For example, uploading three files labeled `User manual`, `설치 가이드`, and `테스트 결과` will produce the summary `User manual, 설치 가이드, 테스트 결과`.
