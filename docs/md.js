/* Minimal markdown → HTML for the docs site's fetched .md pages.
   Auto-runs in browsers on any <div class="md" data-src="...">.
   Exports renderMarkdown for node-based tests. */

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function inline(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, function (_, c) { return "<code>" + c + "</code>"; });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s;
}

function renderMarkdown(md) {
  var lines = md.replace(/\r\n?/g, "\n").split("\n");
  var out = [], i = 0;
  while (i < lines.length) {
    var line = lines[i];
    var m;
    if (m = line.match(/^```/)) {
      var buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++; // closing fence
      out.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>");
      continue;
    }
    if (m = line.match(/^(#{1,4})\s+(.*)/)) {
      var lvl = m[1].length;
      out.push("<h" + lvl + ">" + inline(m[2]) + "</h" + lvl + ">");
      i++; continue;
    }
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) { out.push("<hr>"); i++; continue; }
    if (/^\|/.test(line)) {
      var rows = [];
      while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
      var parse = function (r) {
        return r.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map(function (c) { return c.trim(); });
      };
      var head = parse(rows[0]);
      var body = rows.slice(1).filter(function (r) { return !/^[\s|:-]+$/.test(r); }).map(parse);
      var t = "<table><thead><tr>" + head.map(function (c) { return "<th>" + inline(c) + "</th>"; }).join("") + "</tr></thead><tbody>";
      t += body.map(function (r) {
        return "<tr>" + r.map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>";
      }).join("");
      t += "</tbody></table>";
      out.push(t);
      continue;
    }
    if (/^>/.test(line)) {
      var q = [];
      while (i < lines.length && /^>/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, ""));
      out.push("<blockquote>" + q.map(inline).join("<br>") + "</blockquote>");
      continue;
    }
    if (/^\s*([-*+])\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      var ordered = /^\s*\d+\./.test(line);
      var ul = [];
      while (i < lines.length && (/^\s*([-*+])\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
        var item = lines[i++].replace(/^\s*([-*+]|\d+\.)\s+/, "");
        var task = item.match(/^\[( |x|X)\]\s*(.*)/);
        if (task) {
          ul.push("<li><label><input type=\"checkbox\" disabled" +
            (task[1] !== " " ? " checked" : "") + "> " + inline(task[2]) + "</label></li>");
        } else {
          ul.push("<li>" + inline(item) + "</li>");
        }
      }
      out.push((ordered ? "<ol>" : "<ul>") + ul.join("") + (ordered ? "</ol>" : "</ul>"));
      continue;
    }
    if (/^\s*$/.test(line)) { i++; continue; }
    var para = [line];
    i++;
    while (i < lines.length && !/^\s*$/.test(lines[i]) &&
         !/^(#{1,4}\s|```|>|[-*+]\s|\d+\.\s|\||-{3,}\s*$)/.test(lines[i])) {
      para.push(lines[i++]);
    }
    out.push("<p>" + para.map(inline).join(" ") + "</p>");
  }
  return out.join("\n");
}

if (typeof document !== "undefined") {
  var el = document.querySelector(".md[data-src]");
  if (el) {
    var src = el.getAttribute("data-src");
    el.innerHTML = '<p class="md-loading">Loading ' + esc(src.split("/").pop()) + ' …</p>';
    fetch(src).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    }).then(function (md) {
      el.innerHTML = renderMarkdown(md);
    }).catch(function (e) {
      el.innerHTML = '<p class="md-loading">Could not load the document (' +
        esc(e.message) + '). <a href="' + esc(src) + '">View the raw file instead</a>.</p>';
    });
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { renderMarkdown: renderMarkdown };
}
