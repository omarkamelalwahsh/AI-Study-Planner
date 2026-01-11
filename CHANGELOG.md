# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-01-11
### Added
- Principal production-grade refactor for Python 3.11 strictness
- Data-only contract: all recommendations and plans are strictly dataset-backed
- Progression ordering: Beginner → Intermediate → Advanced enforced
- Strict sidebar filters for category and level
- Robust error handling for missing data, Python version, and PDF export
- Professional documentation and troubleshooting

### Changed
- Hardened pipeline and planner logic
- Defensive data loading and validation
- No hallucinated content or invented plan sections

### Fixed
- PDF export disables gracefully on Unicode/Arabic error
- No duplicated UI rendering

---

## [1.0.0] - Initial MVP
- Semantic search and basic recommendation pipeline
- Streamlit UI and CLI entry points
