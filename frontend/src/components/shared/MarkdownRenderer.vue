<script setup>
import { computed, onMounted, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  inline: {
    type: Boolean,
    default: false
  }
})

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs-code-block"><code class="language-' + lang + '">' +
          hljs.highlight(str, { language: lang }).value +
          '</code></pre>'
      } catch (__) {}
    }
    return '<pre class="hljs-code-block"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  
  if (props.inline) {
    return md.renderInline(props.content)
  }
  
  return md.render(props.content)
})

const containerRef = ref(null)

onMounted(() => {
  if (containerRef.value) {
    containerRef.value.querySelectorAll('pre code').forEach((block) => {
      if (!block.classList.contains('hljs')) {
        hljs.highlightElement(block)
      }
    })
  }
})
</script>

<template>
  <div
    ref="containerRef"
    class="markdown-renderer"
    :class="{ 'markdown-inline': inline }"
    v-html="renderedContent"
  />
</template>

<style scoped>
.markdown-renderer {
  font-size: inherit;
  line-height: inherit;
  color: inherit;
  word-wrap: break-word;
}

.markdown-renderer :deep(h1),
.markdown-renderer :deep(h2),
.markdown-renderer :deep(h3),
.markdown-renderer :deep(h4),
.markdown-renderer :deep(h5),
.markdown-renderer :deep(h6) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-main);
}

.markdown-renderer :deep(h1) { font-size: 1.5em; }
.markdown-renderer :deep(h2) { font-size: 1.3em; }
.markdown-renderer :deep(h3) { font-size: 1.15em; }
.markdown-renderer :deep(h4) { font-size: 1.05em; }

.markdown-renderer :deep(p) {
  margin: 0 0 12px 0;
  line-height: 1.7;
}

.markdown-renderer :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-renderer :deep(ul),
.markdown-renderer :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-renderer :deep(li) {
  margin: 4px 0;
  line-height: 1.6;
}

.markdown-renderer :deep(ul li) {
  list-style-type: disc;
}

.markdown-renderer :deep(ol li) {
  list-style-type: decimal;
}

.markdown-renderer :deep(li ul),
.markdown-renderer :deep(li ol) {
  margin: 4px 0;
}

.markdown-renderer :deep(strong) {
  font-weight: 600;
  color: var(--text-main);
}

.markdown-renderer :deep(em) {
  font-style: italic;
}

.markdown-renderer :deep(code) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(129, 140, 248, 0.1);
  color: rgba(129, 140, 248, 0.9);
}

.markdown-renderer :deep(pre) {
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.05);
  overflow-x: auto;
}

.markdown-renderer :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 0.85em;
}

.markdown-renderer :deep(.hljs-code-block) {
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.05);
  overflow-x: auto;
}

.markdown-renderer :deep(.hljs-code-block code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-renderer :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid rgba(129, 140, 248, 0.5);
  background: rgba(129, 140, 248, 0.05);
  border-radius: 0 8px 8px 0;
  color: rgba(255, 255, 255, 0.8);
}

.markdown-renderer :deep(blockquote p) {
  margin: 0;
}

.markdown-renderer :deep(table) {
  margin: 12px 0;
  border-collapse: collapse;
  width: 100%;
  font-size: 0.9em;
}

.markdown-renderer :deep(th),
.markdown-renderer :deep(td) {
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  text-align: left;
}

.markdown-renderer :deep(th) {
  background: rgba(99, 102, 241, 0.1);
  font-weight: 600;
}

.markdown-renderer :deep(tr:nth-child(even)) {
  background: rgba(255, 255, 255, 0.02);
}

.markdown-renderer :deep(hr) {
  margin: 16px 0;
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.markdown-renderer :deep(a) {
  color: var(--accent, #6366f1);
  text-decoration: none;
}

.markdown-renderer :deep(a:hover) {
  text-decoration: underline;
}

.markdown-renderer :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

.markdown-renderer :deep(del) {
  text-decoration: line-through;
  opacity: 0.7;
}

.markdown-inline :deep(p) {
  margin: 0;
  display: inline;
}
</style>
