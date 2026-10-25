// SPDX-FileCopyrightText: 2026 Vasiliy Seibert
// SPDX-License-Identifier: MIT
// Load BEFORE the unchanged official viewer bundle.
// draw.io 29.6.6 calls Editor.initMath at bootstrap even for math="0" diagrams.
// Its native loader skips loading when MathJax is already defined. This explicit
// sentinel disables that unused optional loader without modifying the renderer.
// drawio-viewer.js rejects math-enabled inputs while this sentinel is present.
(() => {
  'use strict';
  if (typeof window.MathJax === 'undefined') {
    window.MathJax = Object.freeze({heleShawDisabled: true});
  }
})();
