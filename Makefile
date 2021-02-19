VERSION=0.7
DIST_NAME=gcp-doctor-$(VERSION)

test:
	coverage run --include='gcp_doctor/*' -m pytest

coverage-report:
	coverage report -m

version:
	@echo $(VERSION)

dist:
	# TODO: replace with something based on setuptools?
	rm -rf dist-tmp
	mkdir -p dist-tmp/$(DIST_NAME)
	cp Pipfile Pipfile.lock README.md dist-tmp/$(DIST_NAME)
	mkdir dist-tmp/$(DIST_NAME)/bin
	cp --parents bin/gcp-doctor dist-tmp/$(DIST_NAME)
	cp --parents gcp_doctor/queries/client_secrets.json dist-tmp/$(DIST_NAME)
	find gcp_doctor -name '*.py' -exec cp --parents '{}' dist-tmp/$(DIST_NAME) ';'
	sed -i -e "s/^VERSION =.*/VERSION = '$(VERSION)'/" dist-tmp/$(DIST_NAME)/gcp_doctor/config.py
	chmod -R a+rX dist-tmp
	mkdir -p dist
	tar -C dist-tmp -czf dist/gcp-doctor-$(VERSION).tar.gz --owner=0 --group=0 gcp-doctor-$(VERSION)
	rm -rf dist-tmp

.PHONY: test coverage-report dist