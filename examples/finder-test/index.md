---
title: mmdoc Finder Test
author: test
date: 2026-06-29
tags: test, mmdoc, multimodal
summary: A minimal example mmdoc that checks how macOS Finder displays a dotted directory.
---

# mmdoc Finder Test

This folder is a plain folder. It contains an `index.md` and a single image file.

## Sample image

The image below is a real PNG file co-located in this folder. The alt text is the
search surface and the semantic summary:

![Three horizontal color bands — blue on top, yellow in the middle, red on the bottom](img-001.png)

If you are reading this on GitHub, the image above renders inline because the path
is relative. macOS Finder treats an unregistered `.mmdoc` extension as an ordinary
browsable folder, so both `index.md` and `img-001.png` are directly visible.
