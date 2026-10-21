# Changelog

All notable changes to Simility are documented here.

## [1.3.3] - 2026-10-21

### Added

- Added an in-app version label in the bottom-right footer.
- Added selected-size summaries to matching-file group titles. The summary is shown only when that group contains selected files.
- Added the total selected file size to the footer selection summary.
- Added a startup footer message that guides users to select a folder when no previous folder can be restored.
- Added **Simplify file names before checking for similarity**. When enabled, dashes, underscores, periods, and plus signs are treated as spaces during matching while original filenames remain unchanged in results.
- Added a persistent **Select File Types** modal with alphabetical type groups for Apps, Codes, Compressed, Documents, Music, Pictures, and Videos.
- Added group-level and individual file-extension selection, along with Select All, Reverse Selection, and Clear Selection controls.
- Added persistent custom file types, entered as space-separated extensions and normalized to lowercase.

### Changed

- Searches now respect the selected built-in and custom file-type filters.
- Updated the application version to `1.3.3`.
