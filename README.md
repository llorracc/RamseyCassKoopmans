# RamseyCassKoopmans

The handout on the Ramsey/Cass-Koopmans model for the Intertemporal Choice course, and the notebook that
solves the model and draws its figures.

- `RamseyCassKoopmans.tex` and `RamseyCassKoopmans.pdf` are the handout. Its source is the chapter
  [The Ramsey/Cass-Koopmans (RCK) Model](https://intertemporal-choice.github.io/content/growth/ramseycasskoopmans/)
  of the book *Intertemporal Choice*: edits start there, and `./check-book-sync.py` reports any
  difference between the two, and any object the handout writes as a raw letter instead of its macro.
- `RamseyCassKoopmans.ipynb` is a copy of the notebook beside the book's chapter. It writes the figures in
  `Figures/`. Run it in
  [Binder](https://mybinder.org/v2/gh/llorracc/RamseyCassKoopmans/master?labpath=RamseyCassKoopmans.ipynb)
  or [Colab](https://colab.research.google.com/github/llorracc/RamseyCassKoopmans/blob/master/RamseyCassKoopmans.ipynb).
- Build the PDF with `latexmk`. `latexmkrc` puts the vendored `@resources/` (from
  [econ-ark-tools](https://github.com/econ-ark/econ-ark-tools)) first on TeX's search paths, and the
  notation comes from its registry.
