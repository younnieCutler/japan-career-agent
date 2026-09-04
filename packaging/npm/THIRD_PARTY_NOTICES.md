# Third-party notices

The npm package does not bundle uv in its registry tarball. During installation it downloads the
platform-specific uv 0.12.7 binary directly from the official
[Astral uv release](https://github.com/astral-sh/uv/releases/tag/0.12.7), verifies the pinned
SHA-256 digest, and keeps that binary inside the npm package's private runtime directory.

uv is distributed by Astral under the MIT License or the Apache License 2.0. See the upstream
repository for its source and license texts: https://github.com/astral-sh/uv
