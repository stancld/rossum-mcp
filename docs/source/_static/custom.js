document.addEventListener('DOMContentLoaded', function() {
    // Detect if we are viewing a versioned page
    // Matches both legacy (e.g. /source/2.1.0/...) and new (e.g. /source/rossum-mcp-2.2.0/...)
    var pathParts = window.location.pathname.split('/');
    var sourceIdx = pathParts.indexOf('source');
    var currentVersion = null;
    if (sourceIdx !== -1 && sourceIdx + 1 < pathParts.length) {
        var candidate = pathParts[sourceIdx + 1];
        if (/^(rossum-(mcp|agent)-\d+\.\d+|\d+\.\d+)/.test(candidate)) {
            currentVersion = candidate;
        }
    }

    // Add version selector under sidebar brand text
    var brandText = document.querySelector('.sidebar-brand-text');
    if (brandText) {
        var container = document.createElement('div');
        container.className = 'sidebar-version-selector';

        // Resolve base path to /source/ root
        var basePath = window.location.pathname;
        if (sourceIdx !== -1) {
            basePath = pathParts.slice(0, sourceIdx + 1).join('/') + '/';
        }

        var select = document.createElement('select');
        select.id = 'docs-version-select';

        var latestOpt = document.createElement('option');
        latestOpt.value = basePath;
        latestOpt.textContent = 'latest';
        if (!currentVersion) latestOpt.selected = true;
        select.appendChild(latestOpt);

        select.addEventListener('change', function() {
            window.location.href = this.value;
        });

        container.appendChild(select);
        brandText.parentNode.insertBefore(container, brandText.nextSibling);

        // Fetch versions.json and populate dropdown
        var versionsUrl = basePath + 'versions.json';
        fetch(versionsUrl)
            .then(function(resp) { return resp.ok ? resp.json() : []; })
            .then(function(versions) {
                versions.forEach(function(v) {
                    var opt = document.createElement('option');
                    opt.value = basePath + v + '/';
                    // Format label: "rossum-mcp-2.2.0" -> "rossum-mcp v2.2.0", "2.1.0" -> "v2.1.0"
                    var pkgMatch = v.match(/^(rossum-(?:mcp|agent))-(.+)$/);
                    opt.textContent = pkgMatch ? pkgMatch[1] + ' v' + pkgMatch[2] : 'v' + v;
                    if (currentVersion === v) opt.selected = true;
                    select.appendChild(opt);
                });
            })
            .catch(function() {});
    }

    // Hide class prefix from method names in sidebar
    var methodLinks = document.querySelectorAll('li.toctree-l4 a code span.pre');
    methodLinks.forEach(function(span) {
        var fullText = span.textContent;
        var match = fullText.match(/\.([^.()]+\(\))/);
        if (match) {
            span.textContent = match[1];
        }
    });
});
