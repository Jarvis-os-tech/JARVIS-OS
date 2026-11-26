// Shared by the board, WebGL visualizer and Canvas fallback so links meet Ada.
export const panelDefaults = {
  brief: {x:53.8, y:2.6, w:18.5, h:15.5},
  files: {x:10.7, y:9.9, w:15, h:26.5},
  ideas: {x:10.1, y:55.5, w:15.6, h:40},
  plan: {x:64.7, y:21.1, w:27.5, h:71.8},
  tasks: {x:37.5, y:85, w:14.6, h:14.5},
};

export function orbLayout(width, height, workspace = document.body.classList.contains('has-workspace')) {
  if (!workspace) return {x:width / 2, y:height / 2, radius:Math.min(width * .4, height * .37)};
  if (width <= 1000) return {x:width / 2, y:300, radius:115};
  return {x:width * .427, y:height * .457, radius:Math.min(width * .18, height * .29)};
}
