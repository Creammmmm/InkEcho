# Third-party notices

InkEcho's original source and icons use the MIT license in `LICENSE`.
Dependencies retain their own copyright, license and redistribution terms.
The project's MIT license does not relicense Python, Qt, fonts or other bundled
components. Preserve their notices when redistributing a package.

This inventory was inspected from the locked environment on 2026-10-12.
Development/test tools are not intended to be shipped with the application.
Actual final contents must be checked against the generated package inventory;
the earlier stage-zero probe included a larger, untrimmed Qt distribution.

| Component | Measured version | Upstream license information |
| --- | --- | --- |
| CPython | 3.13.15 | PSF license and component notices; `usr/lib/python3.13/LICENSE.txt` in the standalone runtime |
| PySide6 / Shiboken6 | 6.12.0 | Wheel metadata: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; module/component terms also apply |
| Qt libraries/plugins | 6.12.0 | Module licenses and individual third-party notices; see sources below |
| AppImage type-2 runtime | commit `8f39b89` | MIT plus bundled runtime-library terms recorded in its original license |
| qasync | 0.28.0 | BSD-2-Clause |
| dbus-next | 0.2.3 | MIT |
| keyring | 25.7.0 | MIT |
| SecretStorage / jeepney | 3.5.0 / 0.9.0 | BSD-3-Clause / MIT |
| cryptography / cffi / pycparser | 50.0.2 / 2.1.1 / 3.11 | Apache-2.0 OR BSD-3-Clause / MIT-0 / BSD-3-Clause |
| httpx / httpcore / h11 | 0.28.1 / 1.0.9 / 0.16.0 | BSD-3-Clause / BSD-3-Clause / MIT |
| anyio / idna | 4.15.1 / 3.20 | MIT / BSD-3-Clause |
| certifi | 2026.7.22 | MPL-2.0, including the certificate-bundle terms |
| typing_extensions | 4.16.0 | PSF-2.0 |
| jaraco.classes / jaraco.context / jaraco.functools | 3.4.0 / 6.1.2 / 4.6.0 | MIT |
| more-itertools | 11.1.0 | MIT |
| Noto Sans CJK font, if bundled | installed Noto CJK regular collection | Original upstream copyright and SIL Open Font License in `assets/licenses/Noto-CJK-copyright.txt` |
| libei client library | Ubuntu libei1 1.5.0-3, added 2026-10-15 | Expat (MIT); package copyright retained at `usr/share/doc/inkecho/system/libei1/copyright` |

Python wheel distribution metadata and license directories must be copied with
their runtime modules. The installed PySide wheels in this environment did not
contain actual license text files, so the project retains their official
license texts under `assets/licenses` for inclusion in the AppImage. The `assets/licenses/qt` directory additionally retains the official component
attribution pages, with URL and checksum provenance. Exact bundled Ubuntu
package notices accompany Noto, XCB utility, Kerberos and libei libraries in
`usr/share/doc/inkecho/system`. Generated `inventory.json` records the actual
files, links, dependency versions and downloaded asset hashes.

## Sources and modification

- [CPython 3.13 source](https://github.com/python/cpython/tree/3.13) and
  [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
  describe the Python runtime and its bundled components.
- [PySide6 6.12.0 source](https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.12.0)
  provides the binding source and license texts.
- [Qt 6.12 source archive](https://download.qt.io/archive/qt/6.12/) and
  [Qt third-party notices](https://doc.qt.io/qt-6/licenses-used-in-qt.html)
  identify module-specific source, copyrights and licensing. Qt Multimedia
  includes FFmpeg and other separately licensed code; retain their notices too.
- [AppImage runtime source at the measured revision](https://github.com/AppImage/type2-runtime/tree/8f39b89)
  includes build information. Its retained license also identifies musl,
  libfuse, squashfuse, zstd and zlib components and their upstream terms.
- [Noto CJK source](https://github.com/notofonts/noto-cjk) provides the font and
  corresponding open-font notices.
- [libei source](https://gitlab.freedesktop.org/libinput/libei) provides the client
  library and Expat-license copyright notices. The exact Ubuntu package is pinned
  by URL and SHA-256 in `scripts/packaging/system-deps.json`; its copyright file
  was inspected directly from that verified package.

Qt remains dynamically loaded, and the build does not deliberately prevent
replacement of its shared libraries in an extracted AppImage. Source/build
instructions remain in this repository. License and corresponding-source
requirements should be reviewed against the exact final binaries before a
public binary release; this notice is an inventory and attribution record,
not a claim that every redistribution obligation has been independently audited.
