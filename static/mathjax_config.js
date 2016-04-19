MathJax.Ajax.config.path['Contrib'] = '//cdn.mathjax.org/mathjax/contrib';

MathJax.Hub.Config({
    messageStyle: 'none',
	showMathMenu: false,
	showMathMenuMSIE: false,
	showProcessingMessages: false,
    extensions: [
    	'tex2jax.js'
    ],
	jax: [
		'input/TeX',
		'output/HTML-CSS'
	],
    tex2jax: {
        inlineMath: [['$','$'], ['\\(','\\)']],
        displayMath: [['$$','$$'], ['\\[','\\]']],
        skipTags: ['script','noscript','style'],
    	processEnvironments: false,
    	preview: 'none'
    },
    TeX: {
        extensions: [
            'AMSmath.js',
            'AMSsymbols.js',
            'HTML.js',
            '[Contrib]/xyjax/xypic.js',
            '[Contrib]/img/img.js',
            '[Contrib]/counters/counters.js',
            '[Contrib]/forloop/forloop.js',
            '[Contrib]/forminput/forminput.js'
        ],
		Macros: {
			bbA: '{\\mathbb{A}}',
			bbB: '{\\mathbb{B}}',
			bbF: '{\\mathbb{F}}',
			bbN: '{\\mathbb{N}}',
			bbP: '{\\mathbb{P}}',
			bbQ: '{\\mathbb{Q}}',
			bbR: '{\\mathbb{R}}',
			bbZ: '{\\mathbb{Z}}',

			calA: '{\\mathcal{A}}',
			calB: '{\\mathcal{B}}',
			calC: '{\\mathcal{C}}',
			calD: '{\\mathcal{D}}',
			calF: '{\\mathcal{F}}',
			calG: '{\\mathcal{G}}',
			calI: '{\\mathcal{I}}',
			calK: '{\\mathcal{K}}',
			calM: '{\\mathcal{M}}',
			calN: '{\\mathcal{N}}',
			calO: '{\\mathcal{O}}',
			calR: '{\\mathcal{R}}',
			calS: '{\\mathcal{S}}',

			bfA: '{\\mathbf{A}}',
			bfB: '{\\mathbf{B}}',
			bfa: '{\\mathbf{a}}',
			bfb: '{\\mathbf{b}}',
			bfc: '{\\mathbf{c}}',
			bfe: '{\\mathbf{e}}',
			bfw: '{\\mathbf{w}}',
			bfx: '{\\mathbf{x}}',
			bfy: '{\\mathbf{y}}',
			bfz: '{\\mathbf{z}}',

			floor: ['{\\left\\lfloor #1 \\right\\rfloor}', 1],
			ceil: ['{\\left\\lceil #1 \\right\\rceil}', 1],
			'const': '{\\mathrm{const}}',

			le: '\\leqslant',
			ge: '\\geqslant',
			hat: '\\widehat',
			emptyset: '\\varnothing',
			epsilon: '\\varepsilon'
		}
	}
});