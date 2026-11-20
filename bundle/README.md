# Suhail Health logo bundle

Light and dark full logos, symbol-only marks, monochrome variants, favicons, Apple/PWA icons, a manifest and web integration snippets. The original uploaded image is unchanged in original/.

## Use

- logos/suhail-health-logo-on-light.png or .svg: teal/gold artwork on transparent background, for light surfaces.
- logos/suhail-health-logo-on-dark.png or .svg: pale white/gold artwork on transparent background, for dark surfaces.
- logos/*-mono-ink.* and *-mono-white.*: single-color alternatives.
- symbols/: the same theme treatments without lettering.
- icons/: 192, 512 and 1024px app exports; 180px Apple touch icons; separately padded maskable 512px versions. All app/touch/maskable icons have intentional opaque backgrounds.
- favicons/: theme-specific transparent 16/32/48px PNGs, a 16/32/48/64px ICO with a white tile, and an adaptive SVG for browser light/dark preference.
- head-snippet.html: copyable references. site.webmanifest uses dark app icons by default; switch its entries to light if preferred. Adjust start_url/scope for a subpath deployment.
- preview.html and preview.png: asset overview.

## Formats and fidelity

PNG/WebP assets have real alpha where indicated. The SVG files are raster-backed web compositions, not fully traced vector originals. They preserve their embedded pixel artwork and provide consistent theme/monochrome treatments. Enlarged exports do not create new source detail. Use the native masters or original for further brand work.

The uploaded original is retained byte-for-byte. Production variants were derived using the built-in image-generation editor, with code-native SVG theme treatments and standard size/format exports. The unused drafts with transparency artifacts are not included.

## Integration

Copy this directory to public/bundle/ in a typical Next.js app. Use head-snippet.html as a reference. In React, convert class to className and select the asset based on the actual logo surface. A dark operating system does not guarantee that the header itself is dark. Keep the full logo's aspect ratio. Use symbol-only files at small sizes; do not squeeze the full wordmark into a favicon.

Maskable artwork is intentionally smaller and kept within the central safe area. The ICO is intentionally opaque for contrast on older browsers. Adaptive favicon behavior follows browser/system color preference, separately from any application theme toggle.

No trademark, medical certification or partner endorsement is implied.
