# Data Model: Security Enhancements

## Existing Entities

### Contestant
- Fields: id, name, nickname, age
- Security: Data must be anonymized in logs, stored encrypted

### Video
- Fields: id, path, metadata
- Security: Access controls required, no sensitive data in metadata

### FaceEmbedding
- Fields: id, contestant_id, embedding_vector
- Security: Must be encrypted at rest and in transit

## Security Requirements
- All biometric data must be encrypted
- Access logging with data anonymization
- No external data transmission without explicit consent

## Validation Rules
- Input sanitization for all data sources
- Encryption verification for sensitive fields
- Access control enforcement for admin operations