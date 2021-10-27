window.MathJax = {
        options: {
            renderActions: {
                addMenu: [0, '', '']
            },
            skipHtmlTags: [
                "svg",
                "script",
                "noscript",
                "style",
                "textarea",
                "pre",
                "code"
            ]
        },
        startup: {
            typeset: false,
            ready: () => {
                MathJax.startup.defaultReady();
                reveal.typesetMath();
            }
        },
        tex: {
            inlineMath: [["\\(", "\\)"]],
            displayMath: [["\\[", "\\]"]],
            macros: {
                bbA: "{\\mathbb{A}}",
                bbB: "{\\mathbb{B}}",
                bbF: "{\\mathbb{F}}",
                bbN: "{\\mathbb{N}}",
                bbP: "{\\mathbb{P}}",
                bbQ: "{\\mathbb{Q}}",
                bbR: "{\\mathbb{R}}",
                bbZ: "{\\mathbb{Z}}",
                calA: "{\\mathcal{A}}",
                calB: "{\\mathcal{B}}",
                calC: "{\\mathcal{C}}",
                calD: "{\\mathcal{D}}",
                calF: "{\\mathcal{F}}",
                calG: "{\\mathcal{G}}",
                calI: "{\\mathcal{I}}",
                calM: "{\\mathcal{M}}",
                calN: "{\\mathcal{N}}",
                calO: "{\\mathcal{O}}",
                calR: "{\\mathcal{R}}",
                calS: "{\\mathcal{S}}",
                bfA: "{\\mathbf{A}}",
                bfa: "{\\mathbf{a}}",
                bfb: "{\\mathbf{b}}",
                bfc: "{\\mathbf{c}}",
                bfe: "{\\mathbf{e}}",
                bfw: "{\\mathbf{w}}",
                bfx: "{\\mathbf{x}}",
                bfy: "{\\mathbf{y}}",
                bfz: "{\\mathbf{z}}",
                floor: ["{\\left\\lfloor #1 \\right\\rfloor}", 1],
                ceil: ["{\\left\\lceil #1 \\right\\rceil}", 1],
                le: "\\leqslant",
                ge: "\\geqslant",
                hat: "\\widehat",
                emptyset: "\\varnothing",
                epsilon: "\\varepsilon"
            }
        }
    };