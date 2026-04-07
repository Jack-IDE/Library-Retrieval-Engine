# Images and Media

## SVG Icons

SVG is the correct format for icons. It scales perfectly, can be styled with CSS, and adds zero download weight when inlined.

**Inline SVG** (best for icons that need CSS color control):
```html
<svg class="icon" aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24">
  <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
```

`aria-hidden="true"` hides the icon from screen readers. `focusable="false"` prevents SVGs from being tab-focusable in IE/Edge. `currentColor` makes the stroke inherit the CSS `color` property of the parent element.

**SVG sprite** (best for repeated icons):
```html
<!-- Sprite definition (hidden, usually at top of body) -->
<svg style="display:none">
  <symbol id="icon-arrow-right" viewBox="0 0 24 24">
    <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" fill="none"/>
  </symbol>
  <symbol id="icon-check" viewBox="0 0 24 24">
    <path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" fill="none"/>
  </symbol>
</svg>

<!-- Usage anywhere in the document -->
<svg class="icon" aria-hidden="true" focusable="false" width="20" height="20">
  <use href="#icon-arrow-right"/>
</svg>
```

```css
.icon {
  width: 1em;
  height: 1em;
  flex-shrink: 0;
  vertical-align: -0.125em; /* optical alignment with text */
}
```

## Background Images

```css
/* Full-cover background image */
.hero {
  background-image: url('hero.webp');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

/* With overlay for text legibility */
.hero {
  background-image:
    linear-gradient(rgb(0 0 0 / 0.5), rgb(0 0 0 / 0.5)),
    url('hero.webp');
}

/* Responsive background using image-set() */
.hero {
  background-image: image-set(
    url('hero.avif') type('image/avif'),
    url('hero.webp') type('image/webp'),
    url('hero.jpg')  type('image/jpeg')
  );
}
```

## Aspect Ratio

`aspect-ratio` replaces the old padding-top hack for maintaining proportions:

```css
/* Old hack — do not use */
.video-wrapper { padding-top: 56.25%; position: relative; }
.video-wrapper iframe { position: absolute; inset: 0; width: 100%; height: 100%; }

/* Modern approach */
.video-wrapper {
  aspect-ratio: 16 / 9;
  width: 100%;
}
.video-wrapper iframe {
  width: 100%;
  height: 100%;
}

/* Common ratios */
.square      { aspect-ratio: 1; }
.photo       { aspect-ratio: 4 / 3; }
.widescreen  { aspect-ratio: 16 / 9; }
.ultrawide   { aspect-ratio: 21 / 9; }
.portrait    { aspect-ratio: 3 / 4; }
.golden      { aspect-ratio: 1.618; }

/* Card image that fills its container and crops */
.card__image {
  aspect-ratio: 3 / 2;
  object-fit: cover;
  width: 100%;
}
```

## The picture Element

`<picture>` provides art direction — serving different image compositions (not just sizes) at different breakpoints:

```html
<picture>
  <!-- Portrait crop for narrow screens -->
  <source
    media="(max-width: 640px)"
    srcset="hero-portrait.webp"
    type="image/webp"
  >
  <!-- Landscape crop for wider screens, with resolution switching -->
  <source
    media="(min-width: 641px)"
    srcset="hero-800.webp 800w, hero-1200.webp 1200w, hero-1600.webp 1600w"
    sizes="100vw"
    type="image/webp"
  >
  <!-- Fallback -->
  <img
    src="hero-1200.jpg"
    alt="Hero image"
    width="1200"
    height="600"
  >
</picture>
```

The browser uses the first `<source>` whose `media` and `type` conditions match. The `<img>` is the fallback and provides `alt`, `width`, and `height`.

## Video

```html
<video
  class="video"
  width="1280"
  height="720"
  poster="video-poster.jpg"
  preload="metadata"
  controls
  playsinline
  aria-label="Product demo video"
>
  <source src="demo.webm" type="video/webm">
  <source src="demo.mp4"  type="video/mp4">
  <track kind="subtitles" src="demo.en.vtt" srclang="en" label="English" default>
  <p>Your browser does not support video. <a href="demo.mp4">Download the video.</a></p>
</video>
```

For autoplay background video (must be muted to autoplay in most browsers):

```html
<video
  class="bg-video"
  autoplay
  muted
  loop
  playsinline
  aria-hidden="true"
  preload="none"
>
  <source src="background.webm" type="video/webm">
  <source src="background.mp4"  type="video/mp4">
</video>
```

```css
.bg-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: -1;
}

/* Pause for reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .bg-video { display: none; }
}
```

## Lazy Loading

Native lazy loading with `loading="lazy"`:

```html
<!-- Images and iframes support native lazy loading -->
<img src="image.jpg" loading="lazy" alt="...">
<iframe src="map.html" loading="lazy" title="Map"></iframe>
```

Do not add `loading="lazy"` to:
- The LCP image (usually the hero image — it must load immediately)
- Images in the initial viewport
- Images that are likely to be in the viewport on first render

For more control, use Intersection Observer to load images on demand:

```javascript
const lazyImages = document.querySelectorAll('img[data-src]');

const imageObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const img = entry.target;
      img.src = img.dataset.src;
      if (img.dataset.srcset) img.srcset = img.dataset.srcset;
      img.removeAttribute('data-src');
      imageObserver.unobserve(img);
    }
  });
}, { rootMargin: '200px' });  // start loading 200px before entering viewport

lazyImages.forEach(img => imageObserver.observe(img));
```

## Figures and Captions

Use `<figure>` and `<figcaption>` for images that are referenced in surrounding content and need captions:

```html
<figure>
  <img
    src="diagram.png"
    alt="Diagram showing the three-tier architecture with client, server, and database layers"
    width="800"
    height="500"
    loading="lazy"
  >
  <figcaption>
    Figure 1: Three-tier architecture. The client communicates exclusively with the
    server tier. The server tier manages all database access.
  </figcaption>
</figure>
```

```css
figure {
  margin: var(--space-8) 0;
}

figcaption {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  text-align: center;
}
```

The `alt` text and the `<figcaption>` serve different purposes. `alt` is a textual replacement for the image (read when the image is not available or to screen reader users). `figcaption` is supplementary contextual information shown to all users.

## Image Optimization Checklist

Converting images to the right formats at build time:

```bash
# Convert JPEG to WebP using cwebp
cwebp -q 85 photo.jpg -o photo.webp

# Convert JPEG to AVIF using avifenc
avifenc --min 20 --max 40 photo.jpg photo.avif

# Resize to specific width
convert photo.jpg -resize 1200x photo-1200.jpg

# Generate responsive sizes in one command with ImageMagick
for width in 400 800 1200 1600; do
  convert photo.jpg -resize ${width}x photo-${width}.jpg
done
```

Quick reference: AVIF is 40–50% smaller than JPEG at equivalent quality. WebP is 25–35% smaller. Use AVIF with WebP as fallback in `<picture>`. For PNG images, try AVIF or WebP lossless mode first. For SVG, use an SVG optimizer like svgo.
