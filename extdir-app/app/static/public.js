(function () {
  var q = document.getElementById("q"), body = document.querySelector("#t tbody"),
      count = document.getElementById("count"), chips = document.getElementById("depts"), dept = "", timer;
  function td(text, cls) { var c = document.createElement("td"); c.textContent = text == null ? "" : text; if (cls) c.className = cls; return c; }
  function load() {
    fetch("/api/public/search?q=" + encodeURIComponent(q.value) + (dept ? "&dept=" + dept : ""))
      .then(function (r) { if (r.status === 429) throw new Error("查詢太頻繁，請稍後再試"); return r.json(); })
      .then(function (d) {
        if (!chips.children.length) {
          [{ id: "", name: "全部" }].concat(d.depts).forEach(function (x) {
            var b = document.createElement("button"); b.textContent = x.name; b.dataset.id = x.id; if (!x.id) b.className = "on";
            b.onclick = function () { dept = this.dataset.id; [].forEach.call(chips.children, function (c) { c.className = ""; }); this.className = "on"; load(); };
            chips.appendChild(b);
          });
        }
        body.textContent = "";
        d.rows.forEach(function (r) {
          var tr = document.createElement("tr");
          [td(r.name), td(r.dept), td(r.title), td(r.ext, "ext"), td(r.grade)].forEach(function (c) { tr.appendChild(c); });
          body.appendChild(tr);
        });
        count.textContent = d.rows.length + " 筆";
      }).catch(function (e) { count.textContent = e.message; });
  }
  q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(load, 200); });
  load();
})();
