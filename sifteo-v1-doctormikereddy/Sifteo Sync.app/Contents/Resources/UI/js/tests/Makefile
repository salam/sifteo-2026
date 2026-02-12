BROWSER = open
PHANTOMJS = phantomjs

test: test-phantomjs

test-browser:
	$(BROWSER) unit/runner.html

test-phantomjs:
	$(PHANTOMJS) unit/vendor/phantomjs-mocha/scripts/mocha.js unit/runner/phantomjs.html

.PHONY: test-browser test-phantomjs
