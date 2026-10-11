# Retained upstream licenses

The GPL-2.0-only, GPL-3.0-only and LGPL-3.0-only texts were downloaded unchanged
from the official PySide repository at tag `v6.12.0` on 2026-10-12:

```text
https://code.qt.io/cgit/pyside/pyside-setup.git/plain/LICENSES/GPL-2.0-only.txt?h=v6.12.0
https://code.qt.io/cgit/pyside/pyside-setup.git/plain/LICENSES/GPL-3.0-only.txt?h=v6.12.0
https://code.qt.io/cgit/pyside/pyside-setup.git/plain/LICENSES/LGPL-3.0-only.txt?h=v6.12.0
```

Verified local SHA-256:

```text
8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643  GPL-2.0-only.txt
8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903  GPL-3.0-only.txt
da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768  LGPL-3.0-only.txt
```

`AppImage-runtime-LICENSE.txt` is the unchanged upstream license from runtime
commit `8f39b89`. `Noto-CJK-copyright.txt` is copied unchanged from the installed
Ubuntu `fonts-noto-cjk` package's copyright file. These notices do not relicense
those dependencies under InkEcho's own MIT license.

`qt/` retains 59 official Qt 6.12 component attribution pages for the selected
Core/GUI/Network/DBus/Widgets/Multimedia/Svg/Wayland/image-format modules,
including FFmpeg's notices. They were downloaded on 2026-10-12; `qt/sources.json`
records original URLs and SHA-256 digests. The pages remain unmodified, including
their documentation copyright and license statements. They describe possible
upstream components, not a claim that every listed component is in the binary.
`GFDL-1.3.txt` and `LGPL-2.1.txt` were copied unchanged from Ubuntu's
`/usr/share/common-licenses` for the documentation and FFmpeg references.
The build additionally retains the exact Ubuntu package copyright files for
bundled Noto and utility libraries, separately from these reference notices.
