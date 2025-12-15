cd docs
uv run quartodoc build
uv run quarto render --to html --execute
cd ..