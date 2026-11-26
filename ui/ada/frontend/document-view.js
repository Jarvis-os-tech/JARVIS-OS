// A document reader built from text nodes. Project Markdown is never executed as HTML.
const element = (tag, className = '', text) => {
  const result = document.createElement(tag);
  result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
};
const heading = line => line.match(/^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
const listItem = line => line.match(/^( *)([-+*]|\d+[.)])\s+(.*)$/);
const fence = line => line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
const rule = line => /^ {0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/.test(line);
const tableRow = line => line.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
const tableDivider = line => line?.includes('|') && tableRow(line).every(cell => /^:?-{3,}:?$/.test(cell));

function blocks(lines, depth = 0) {
  if (depth > 8) return [{type:'paragraph', text:lines.join('\n')}];
  const result = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const code = fence(line), h = heading(line), item = listItem(line);
    if (code) {
      const body = []; i++;
      const end = new RegExp(`^ {0,3}${code[1][0]}{${code[1].length},}\\s*$`);
      while (i < lines.length && !end.test(lines[i])) body.push(lines[i++]);
      if (i < lines.length) i++;
      result.push({type:'code', text:body.join('\n'), language:code[2].trim()});
    } else if (h) {
      result.push({type:'heading', level:h[1].length, text:h[2]}); i++;
    } else if (rule(line)) {
      result.push({type:'rule'}); i++;
    } else if (/^ {0,3}>/.test(line)) {
      const quoted = [];
      while (i < lines.length && /^ {0,3}>/.test(lines[i])) quoted.push(lines[i++].replace(/^ {0,3}> ?/, ''));
      result.push({type:'quote', blocks:blocks(quoted, depth + 1)});
    } else if (item) {
      const indent = item[1].length, ordered = /^\d/.test(item[2]), items = [];
      while (i < lines.length) {
        const current = listItem(lines[i]);
        if (!current || current[1].length !== indent || /^\d/.test(current[2]) !== ordered) break;
        const check = current[3].match(/^\[([ xX])\]\s+(.*)$/);
        const content = [check ? check[2] : current[3]], width = current[1].length + current[2].length + 1;
        i++;
        while (i < lines.length) {
          if (!lines[i].trim()) {
            if (lines[i + 1] && /^ +/.test(lines[i + 1]) && lines[i + 1].search(/\S/) > indent) { content.push(''); i++; continue; }
            break;
          }
          if (lines[i].search(/\S/) <= indent) break;
          content.push(lines[i].slice(Math.min(width, lines[i].search(/\S/)))); i++;
        }
        items.push({checked:check ? check[1].toLowerCase() === 'x' : null, blocks:blocks(content, depth + 1)});
        if (!lines[i]?.trim() && listItem(lines[i + 1] || '')?.[1].length === indent) i++;
      }
      result.push({type:'list', ordered, start:ordered ? parseInt(item[2], 10) : 1, items});
    } else if (line.includes('|') && tableDivider(lines[i + 1])) {
      const headers = tableRow(line), alignment = tableRow(lines[i + 1]).map(cell => cell.endsWith(':') ? cell.startsWith(':') ? 'center' : 'right' : 'left');
      const rows = []; i += 2;
      while (i < lines.length && lines[i].trim() && lines[i].includes('|')) rows.push(tableRow(lines[i++]));
      result.push({type:'table', headers, alignment, rows});
    } else if (/^ {0,3}(?:=+|-+)\s*$/.test(lines[i + 1] || '')) {
      result.push({type:'heading', level:lines[i + 1].trim().startsWith('=') ? 1 : 2, text:line.trim()}); i += 2;
    } else {
      const paragraph = [line]; i++;
      while (i < lines.length && lines[i].trim() && !heading(lines[i]) && !listItem(lines[i]) && !fence(lines[i]) && !rule(lines[i]) && !/^ {0,3}>/.test(lines[i]) && !tableDivider(lines[i + 1])) paragraph.push(lines[i++]);
      result.push({type:'paragraph', text:paragraph.join('\n')});
    }
  }
  return result;
}

function projectPath(value, currentPath) {
  if (/^[a-z][a-z\d+.-]*:/i.test(value) || value.startsWith('//') || value.startsWith('#')) return null;
  let decoded;
  try { decoded = decodeURIComponent(value); } catch { return null; }
  if (decoded.includes('\\') || decoded.includes('?') || decoded.includes('#')) return null;
  const parts = decoded.startsWith('/') ? [] : currentPath.split('/').slice(0, -1);
  for (const part of decoded.split('/')) {
    if (!part || part === '.') continue;
    if (part === '..') { if (!parts.length) return null; parts.pop(); }
    else { if (part.startsWith('.')) return null; parts.push(part); }
  }
  return parts.join('/') || null;
}

function inline(target, text, context = {}, depth = 0) {
  if (depth > 6) { target.append(document.createTextNode(text)); return; }
  const pattern = /\\(?<escaped>[\\`*{}\[\]()#+.!_>~-])|(?<image>!)?\[(?<label>[^\]\n]*)\]\((?<url>[^)\n]+)\)|`(?<code>[^`\n]+)`|\*\*(?<bold>[^*]+)\*\*|__(?<strong>[^_]+)__|~~(?<strike>[^~]+)~~|\*(?<italic>[^*\n]+)\*|_(?<em>[^_\n]+)_/g;
  let offset = 0;
  for (const match of text.matchAll(pattern)) {
    target.append(document.createTextNode(text.slice(offset, match.index)));
    offset = match.index + match[0].length;
    const token = match.groups;
    if (token.escaped !== undefined) target.append(document.createTextNode(token.escaped));
    else if (token.url !== undefined) {
      const destination = token.url.trim(), path = projectPath(destination, context.path || '');
      if (token.image && path && /\.(png|jpe?g|webp)$/i.test(path) && context.fileURL) {
        const image = element('img', 'document-inline-image'); image.alt = token.label; image.loading = 'lazy'; image.src = context.fileURL(path);
        target.append(image);
      } else if (!token.image && path && context.openFile) {
        const link = element('button', 'document-file-link'); link.type = 'button';
        inline(link, token.label, {}, depth + 1); link.onclick = () => context.openFile(path); target.append(link);
      } else if (!token.image && /^https?:\/\//i.test(destination)) {
        const link = element('a'); link.href = destination; link.target = '_blank'; link.rel = 'noopener noreferrer';
        inline(link, token.label, {}, depth + 1); target.append(link);
      } else target.append(document.createTextNode(token.label || destination));
    } else {
      const name = token.code !== undefined ? 'code' : token.bold !== undefined || token.strong !== undefined ? 'strong' : token.strike !== undefined ? 's' : 'em';
      const content = token.code ?? token.bold ?? token.strong ?? token.strike ?? token.italic ?? token.em;
      const child = element(name);
      if (name === 'code') child.textContent = content;
      else inline(child, content, context, depth + 1);
      target.append(child);
    }
  }
  target.append(document.createTextNode(text.slice(offset)));
}

function renderBlocks(target, content, context) {
  for (const block of content) {
    if (block.type === 'heading') { const h = element('h' + Math.min(6, Math.max(2, block.level))); inline(h, block.text, context); target.append(h); }
    else if (block.type === 'paragraph') { const p = element('p'); inline(p, block.text, context); target.append(p); }
    else if (block.type === 'rule') target.append(element('hr'));
    else if (block.type === 'code') {
      const figure = element('figure', 'document-code');
      if (block.language) figure.append(element('figcaption', '', block.language));
      const pre = element('pre'); pre.append(element('code', '', block.text)); figure.append(pre); target.append(figure);
    } else if (block.type === 'quote') {
      const quote = element('blockquote'); renderBlocks(quote, block.blocks, context); target.append(quote);
    } else if (block.type === 'list') {
      const list = element(block.ordered ? 'ol' : 'ul'); if (block.ordered) list.start = block.start;
      for (const item of block.items) {
        const li = element('li', item.checked === null ? '' : 'document-task' + (item.checked ? ' is-complete' : ''));
        if (item.checked !== null) { const marker = element('span', 'document-task-mark', item.checked ? '✓' : ''); marker.setAttribute('role', 'img'); marker.setAttribute('aria-label', item.checked ? 'Completed step' : 'Incomplete step'); li.append(marker); }
        const body = element('div', 'document-list-content'); renderBlocks(body, item.blocks, context); li.append(body); list.append(li);
      }
      target.append(list);
    } else if (block.type === 'table') {
      const wrap = element('div', 'document-table'); wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Document table');
      const table = element('table'), head = element('thead'), row = element('tr');
      block.headers.forEach((text, i) => { const cell = element('th'); cell.scope = 'col'; cell.style.textAlign = block.alignment[i]; inline(cell, text, context); row.append(cell); });
      head.append(row); table.append(head); const body = element('tbody');
      for (const values of block.rows) { const row = element('tr'); block.headers.forEach((_, i) => { const cell = element('td'); cell.style.textAlign = block.alignment[i]; inline(cell, values[i] || '', context); row.append(cell); }); body.append(row); }
      table.append(body); wrap.append(table); target.append(wrap);
    }
  }
}

function tasks(content) {
  const all = [];
  for (const block of content) {
    if (block.items) for (const item of block.items) { if (item.checked !== null) all.push(item.checked); all.push(...tasks(item.blocks)); }
    if (block.blocks) all.push(...tasks(block.blocks));
  }
  return all;
}

export function renderMarkdown(text, context = {}) {
  const body = element('div', 'document-prose');
  renderBlocks(body, blocks(text.replace(/\r\n?/g, '\n').split('\n')), context);
  return body;
}

// Use the reader's parser for the board roadmap, including fenced-code handling.
export function documentOutline(content) {
  const parsed = blocks(content.replace(/\r\n?/g, '\n').split('\n'));
  const titleIndex = parsed.findIndex(block => block.type === 'heading' && block.level === 1);
  if (titleIndex >= 0) parsed.splice(titleIndex, 1);
  const level = Math.min(...parsed.filter(block => block.type === 'heading').map(block => block.level));
  return parsed.filter(block => block.type === 'heading' && block.level === level).map((block, i) => {
    const label = element('span'); inline(label, block.text);
    return {number:i + 1, title:label.textContent};
  });
}

export function documentView({content, path, projectName, fileURL, openFile, kind, title:providedTitle}) {
  const markdown = kind === 'markdown', context = {path, fileURL, openFile};
  const parsed = markdown ? blocks(content.replace(/\r\n?/g, '\n').split('\n')) : [];
  const titleIndex = parsed.findIndex(block => block.type === 'heading' && block.level === 1);
  const title = providedTitle || (titleIndex >= 0 ? parsed[titleIndex].text : path.split('/').pop().replace(/\.[^.]+$/, '').replace(/[-_]/g, ' '));
  if (titleIndex >= 0 && !providedTitle) parsed.splice(titleIndex, 1);
  const level = Math.min(...parsed.filter(block => block.type === 'heading').map(block => block.level));
  const sections = [], introduction = [];
  for (const block of parsed) {
    if (block.type === 'heading' && block.level === level) sections.push({title:block.text, blocks:[]});
    else (sections.at(-1)?.blocks || introduction).push(block);
  }
  const checked = tasks(parsed), words = content.trim().split(/\s+/).filter(Boolean).length;
  const article = element('article', 'document-reader'); article.setAttribute('aria-label', title);
  const hero = element('header', 'document-hero');
  hero.append(element('p', 'document-eyebrow', `${projectName || 'ADA'} / ${kind === 'pdf' ? 'PDF · EXTRACTED TEXT' : kind === 'code' ? 'SOURCE FILE' : /plan/i.test(path + ' ' + title) ? 'PROJECT PLAN' : 'PROJECT DOCUMENT'}`));
  const h1 = element('h1'); inline(h1, title, context); hero.append(h1);
  const meta = element('div', 'document-meta');
  if (sections.length) meta.append(element('span', '', `${sections.length} sections`));
  if (checked.length) meta.append(element('span', '', `${checked.filter(Boolean).length} / ${checked.length} steps complete`));
  meta.append(element('span', '', `${Math.max(1, Math.ceil(words / 220))} min read`)); hero.append(meta);
  article.append(hero);
  const layout = element('div', 'document-layout'), main = element('div', 'document-main');
  if (sections.length) {
    const aside = element('aside', 'document-outline'); const nav = element('nav'); nav.setAttribute('aria-label', 'Document sections');
    aside.append(element('p', 'document-outline-label', 'IN THIS DOCUMENT'));
    sections.forEach((section, i) => {
      const button = element('button', 'document-section-link'); button.type = 'button';
      button.append(element('span', 'document-section-number', String(i + 1).padStart(2, '0')));
      const label = element('span'); inline(label, section.title); button.append(label);
      button.onclick = () => main.querySelectorAll('[data-document-section]')[i].scrollIntoView({block:'start', behavior:'instant'});
      nav.append(button);
    });
    aside.append(nav, element('p', 'document-voice-hint', 'Ask Ada to explain a section or make a change.'));
    layout.append(aside);
  } else layout.classList.add('without-outline');
  if (markdown) {
    if (introduction.length) { const intro = element('div', 'document-intro document-prose'); renderBlocks(intro, introduction, context); main.append(intro); }
    const grid = element('div', 'document-sections');
    sections.forEach((section, i) => {
      const card = element('section', 'document-section'); card.dataset.documentSection = String(i + 1);
      const head = element('header', 'document-section-heading'); head.append(element('span', 'document-section-number', String(i + 1).padStart(2, '0')));
      const h = element('h2'); inline(h, section.title, context); head.append(h); card.append(head);
      card.dataset.sectionTitle = h.textContent;
      const body = element('div', 'document-prose'); renderBlocks(body, section.blocks, context); card.append(body);
      if (body.querySelector('table,pre,h3,h4,h5,h6')) card.classList.add('document-section-wide');
      grid.append(card);
    });
    main.append(grid);
    if (!content.trim()) main.append(element('p', 'empty-copy', 'This file is empty. Tell Ada what you’d like to put in it.'));
  } else if (kind === 'code') {
    const pre = element('pre', 'document-source'); pre.append(element('code', '', content)); main.append(pre);
  } else main.append(element('div', 'document-plain', content || 'No text is available to preview.'));
  layout.append(main); article.append(layout);
  return article;
}
