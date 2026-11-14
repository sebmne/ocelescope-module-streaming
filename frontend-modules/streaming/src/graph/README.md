# Graph viewer (copied from Ocelescope)

A copy of Ocelescope's ELK/Graphviz graph viewer (`GraphFlow`), adapted for models that change while a run is going.

- **Source:** https://github.com/promi4s/ocelescope, commit `8768e6a`,
  `src/frontend/packages/resources/src/components/ResourceView/Viewers/GraphFlow`.
- **License:** see `LICENSE`, copied from the repository.
- **Changes**, each marked "Streaming change" in the code:
  - `hooks/useGraphLayout.ts`: keeps the previous layout visible while the next one is computed and lays out only the
    newest model.
  - `index.tsx`: follows the growing graph after every layout until the user zooms or pans; the fit button resumes it.
    With a `layout` (the union of all frames of a run), it lays out the union once and shows each frame in it.
  - `render/pin.ts`: shows only a frame's elements, at the union's positions, with the frame's labels and annotations.
  - `types.ts`: replaces Ocelescope's internal type module, which the package does not export.
