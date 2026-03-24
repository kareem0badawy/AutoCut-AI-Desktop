# Archived Files

These files have been archived during the refactor to a desktop GUI application.

## image_generator.py
**Reason for archiving:** This file was a complete duplicate of `ai_mapper.py`.
Both files contained identical code for mapping images to timestamps.
The functionality is now in `app/core/ai_mapper.py`.

Note: The original project README described this file as a HuggingFace image generator,
but the actual code was the AI mapping logic. The HuggingFace image generation step
is now documented in the Pipeline Runner UI (Step 2).

## check_names.py
**Reason for archiving:** This was a small debug utility that listed filenames in the
images folders. This functionality is now available in the Assets Manager panel of the GUI.
