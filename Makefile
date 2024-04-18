all:
	python setup.py install

clean:
	rm -rf build dist
	find . -type d \( \
		-name .pytest_cache -o \
		-name .mypy_cache -o \
		-name __pycache__ -o \
		-name '*.egg-info' \
	\) -prune -exec rm -rf \{\} \;

uninstall:
	pip uninstall -q -y recover
