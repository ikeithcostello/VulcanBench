"""Compatibility entry point for the pinned, isolated synthetic validation.

Pass --output and optionally --efforts as documented by --help.
No benchmark tasks are read or submitted.
"""

from smoke_muse_adapter import main

if __name__ == "__main__":
    main()
