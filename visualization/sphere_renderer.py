"""
PyVista rendering for 3D sly sphere visualization.
Handles all visual rendering of tiles, nodes, and markers.
"""

import pyvista as pv
import numpy as np
import vtk
try:
    from astropy.units import brightness_temperature
except ModuleNotFoundError:
    # Optional dependency; not required for math-only unit tests.
    brightness_temperature = None

from visualization.styles import *
from project_utils import viridis_rgb
from models.coordinates import ra_dec_to_xyz

import time

class SphereRenderer:
    """Handles PyVista rendering of the sky sphere and tiles."""

    def __init__(self, fov_size: float = 1.5):
        """Initialize the renderer with a PyVista plotter."""
        self.plotter = None
        self.nodes_visible = True
        self.fov_size = fov_size
        self._schedule_path_head_actor = None

    def create_plotter(self):
        """
        Create and configure a new PyVista plotter.

        :return:
            pv.Plotter: Configures plotter instance
        """
        self.plotter = pv.Plotter()
        return self.plotter

    def add_sphere_wireframe(self):
        """Add the background wireframe sphere to the visualization."""
        # Dark background to match app theme (#0d1117)
        self.plotter.set_background("#0d1117")
        sphere = pv.Sphere(radius=SPHERE_RADIUS)
        self.plotter.add_mesh(
            sphere,
            color=COLOR_SPHERE_WIREFRAME,
            style='wireframe',
            opacity=SPHERE_WIREFRAME_OPACITY,
            pickable=False
        )

    def add_tile_patches(self, tiles):
        """
        Add colored tile patches to the visualization.

        :param tiles (list): List of tile dictionaries with 'patch' and 'prob' keys
        """
        all_patches = []
        all_probs = []

        # Calculate corners using fov size
        half_fov = self.fov_size / 2.0

        # West: RA decreases
        # East: RA increases
        # North: Dec increases
        # South: Dec decreases
        for tile in tiles:
            ra = tile['ra']
            dec = tile['dec']
            prob = tile['prob']

            corners = [
                ra_dec_to_xyz(ra - half_fov, dec - half_fov),
                ra_dec_to_xyz(ra + half_fov, dec - half_fov),
                ra_dec_to_xyz(ra + half_fov, dec + half_fov),
                ra_dec_to_xyz(ra - half_fov, dec + half_fov)
            ]

            # # List of the 4 corners of a patch
            vertices = np.array(corners)

            # # Connect 4 vertices in order 0-3
            faces = np.array([4, 0, 1, 2, 3], dtype=np.int64)

            # # PolyData patch
            surface_mesh = pv.PolyData(vertices, faces)

            all_patches.append(surface_mesh)
            all_probs.append(prob)

        # Merge into one mesh
        combined_mesh = pv.merge(all_patches)

        # Assign cell data
        combined_mesh.cell_data['Probability'] = all_probs

        # Add to plotter
        self.plotter.add_mesh(
            combined_mesh,
            scalars='Probability',
            show_scalar_bar=True,
            pickable=False,
            scalar_bar_args=SCALAR_BAR_CONFIG
        )

    def add_node_point_cloud(self, tiles):
        """
        Add node point cloud showing all tile centers.

        :param tiles (list): List of tile dictionaries with 'position' key
        """

        all_positions = np.array([tile['position'] for tile in tiles])
        all_probs = np.array([tile['prob'] for tile in tiles])

        node_cloud = pv.PolyData(all_positions)
        node_cloud.point_data['Probability'] = all_probs

        self.node_actor = self.plotter.add_mesh(
            node_cloud,
            scalars='Probability',
            cmap=PROBABILITY_COLORMAP,
            point_size=NODE_POINT_SIZE,
            render_points_as_spheres=True,
            opacity=NODE_OPACITY_UNSELECTED,
            name='all_nodes',
            show_scalar_bar=False
        )

    def highlight_selected_tile(self, tile, tile_index):
        """"
        Highlight a selected tile by adding a red marker.

        params:
            tile (dict): Tile dictionary with 'mesh' key
            tile_index (int): Index of the tile in tiles list
        """

        center = np.array(tile["position"], dtype=float)
        node = pv.Sphere(
            radius=NODE_RADIUS,
            center=center,
            theta_resolution=0,
            phi_resolution=0
        )

        self.plotter.add_mesh(
            node,
            color=COLOR_NODE_SELECTED,
            name=f'selected_node_{tile_index}',
            reset_camera=False
        )

    def add_toggle_button(self, callback):
        """
        Add a checkbox button to toggle node visibility.

        :param callback (function): Function to call when button is clicked.
        """

        self.plotter.add_checkbox_button_widget(
            callback,
            value=True,
            position=(10, 10),
            size=30,
            border_size=3,
            color_on='green',
            color_off='red'
        )

    def enable_picking(self, callback):
        """
        Enable point picking with left-click.

        :param callback (function): Function to call when a point is clicked.
        """
        if not hasattr(self, "node_actor") or self.node_actor is None:
            return # No nodes yet, so no picking

        # Only allow picking on the node actor
        picker = vtk.vtkPointPicker()
        picker.SetTolerance(0.005)
        picker.PickFromListOn()
        picker.AddPickList(self.node_actor)

        self.plotter.picker = picker

        def _on_pick(picked_point, picker=None):
            if picker is not None and picker.GetPointId() == -1:
                return
            callback(picked_point)

        self.plotter.disable_picking()
        self.plotter.enable_point_picking(
            callback=_on_pick,
            show_message=False,
            show_point=False,
            left_clicking=True,
            use_picker=True
        )

    def clear_selected_tiles(self):
        if not self.plotter:
            return

        # Remove any actor whose name starts with "selected_node"
        for name in list(self.plotter.renderer.actors.keys()):
            if name.startswith('selected_node_'):
                self.plotter.remove_actor(name)
        self.plotter.render()

    def remove_selected_tile_marker(self, tile_index):
        """Remove a single selected marker by tile index."""
        if not self.plotter:
            return

        actor_name = f"selected_node_{tile_index}"
        if actor_name in self.plotter.renderer.actors:
            self.plotter.remove_actor(actor_name)
            self.plotter.render()

    def draw_schedule_labels(self, tiles):
        """
        Draw number of labels next to scheduled tiles.

        :param tiles (list): List of tile dicts, each with:
            - position: (x,y,z)
            - order: 1..n
        """

        if not self.plotter:
            return

        cam = self.plotter.camera_position

        # Remove old labels
        self.clear_schedule_labels()

        # Build label pos and text
        positions = [] # 3D pos
        labels = [] # text labels

        for tile in tiles:
            pos = np.array(tile['position'])
            pos = pos * 1.03
            positions.append(pos)
            labels.append(str(tile['order']))

        # If nothing to draw, stop
        if not positions:
            return

        # Add labels to the plotter
        self.plotter.add_point_labels(
            positions,
            labels,
            font_size=20,
            text_color="white",
            shape=True,
            shape_color="white",
            shape_opacity=0.8,
            name="scheduled_labels"
        )

        self.plotter.camera_position = cam
        self.plotter.render()

    def _ordered_schedule_tiles(self, tiles):
        """Return tiles in schedule order when available."""
        orders = [t.get("order") for t in tiles]
        use_order = all(isinstance(o, int) for o in orders) and len(set(orders)) == len(orders)
        if use_order:
            return [t for _, t in sorted(
                enumerate(tiles),
                key=lambda it: it[1]["order"]
            )]
        return list(tiles)

    def build_schedule_path_geometry(self, tiles, up_to_segment=None):
        """Precompute path points and per-point brightness for schedule animation."""
        if not self.plotter or len(tiles) < 2:
            return None, None

        ordered_tiles = self._ordered_schedule_tiles(tiles)
        n_arcs = len(ordered_tiles) - 1
        if up_to_segment is not None:
            up_to_segment = max(0, min(up_to_segment, n_arcs - 1))
            n_arcs = up_to_segment + 1

        all_points = []
        for i in range(n_arcs):
            p1 = np.asarray(ordered_tiles[i]['position'], dtype=float)
            p2 = np.asarray(ordered_tiles[i + 1]['position'], dtype=float)
            if not np.isfinite(p1).all() or not np.isfinite(p2).all():
                continue
            n1 = np.linalg.norm(p1)
            n2 = np.linalg.norm(p2)
            if n1 == 0 or n2 == 0:
                continue
            p1 = p1 / n1 * SPHERE_RADIUS
            p2 = p2 / n2 * SPHERE_RADIUS
            arc_pts = self._slerp_points(p1, p2, n=60)
            if i > 0:
                arc_pts = arc_pts[1:]
            all_points.append(arc_pts)

        if not all_points:
            return None, None

        path = np.vstack(all_points)

        cam_pos, cam_focal, *_ = self.plotter.camera_position
        cam_pos = np.array(cam_pos, dtype=float)
        cam_focal = np.array(cam_focal, dtype=float)
        forward = cam_focal - cam_pos
        norm = np.linalg.norm(forward)
        if norm == 0:
            return path, np.ones(len(path), dtype=float)
        forward = forward / norm

        depth = np.dot(path - cam_pos, forward)
        d_min = depth.min()
        d_max = depth.max()
        if d_max > d_min:
            depth01 = (depth - d_min) / (d_max - d_min)
        else:
            depth01 = np.zeros_like(depth)
        brightness = 1.0 - depth01
        return path, brightness

    def draw_schedule_path_points(self, path, brightness, max_points=None, show_head=False):
        """Draw a precomputed schedule path, optionally revealing only an initial prefix."""
        if not self.plotter or path is None or len(path) < 2:
            return

        self.clear_schedule_path(render=False)

        if max_points is not None:
            max_points = int(max(2, min(max_points, len(path))))
            visible_path = path[:max_points]
            visible_brightness = brightness[:max_points]
        else:
            visible_path = path
            visible_brightness = brightness

        arc_line = pv.lines_from_points(visible_path)
        arc_line["brightness"] = visible_brightness

        self.plotter.add_mesh(
            arc_line,
            scalars="brightness",
            cmap="Reds",
            line_width=3,
            name="schedule_path",
            scalar_bar_args=None,
            show_scalar_bar=False,
            reset_camera=False,
        )

        if show_head and len(visible_path) > 0:
            self.set_schedule_path_head_position(visible_path[-1], render=False)

        self.plotter.render()

    def begin_schedule_path_flow(self, path, brightness, render=True):
        """
        Start progressive path reveal: short initial segment + head at the leading edge.
        Use update_schedule_path_flow() on each tick to extend the stroke without stutter.
        """
        if not self.plotter or path is None or len(path) < 2:
            return
        self.clear_schedule_path(render=False)
        mesh = pv.lines_from_points(path[:2])
        mesh["brightness"] = brightness[:2]
        self.plotter.add_mesh(
            mesh,
            scalars="brightness",
            cmap="Reds",
            line_width=3,
            name="schedule_path",
            scalar_bar_args=None,
            show_scalar_bar=False,
            reset_camera=False,
        )
        self.set_schedule_path_head_position(path[1], render=render)

    def update_schedule_path_flow(self, path, brightness, num_points, render=True):
        """
        Extend the visible stroke along precomputed path by updating the line actor in place.
        Avoids remove/add each frame (main source of stutter). Head follows the stroke tip.
        """
        if not self.plotter or path is None or len(path) < 2:
            return
        n = max(2, min(int(num_points), len(path)))
        visible_path = path[:n]
        visible_brightness = brightness[:n]
        mesh = pv.lines_from_points(visible_path)
        mesh["brightness"] = visible_brightness
        actor = self.plotter.renderer.actors.get("schedule_path")
        if actor is None:
            self.draw_schedule_path_points(path, brightness, max_points=n, show_head=False)
            self.set_schedule_path_head_position(visible_path[-1], render=render)
            return
        try:
            actor.mapper.SetInputData(mesh)
            actor.mapper.Update()
            bmin = float(mesh["brightness"].min())
            bmax = float(mesh["brightness"].max())
            if bmax > bmin:
                actor.mapper.SetScalarRange(bmin, bmax)
        except Exception:
            self.plotter.remove_actor("schedule_path")
            self.plotter.add_mesh(
                mesh,
                scalars="brightness",
                cmap="Reds",
                line_width=3,
                name="schedule_path",
                scalar_bar_args=None,
                show_scalar_bar=False,
                reset_camera=False,
            )
        self.set_schedule_path_head_position(visible_path[-1], render=False)
        if render:
            self.plotter.render()

    def set_schedule_path_head_position(self, position, render=True):
        """Move or create the animated schedule-path head marker."""
        if not self.plotter or position is None:
            return

        pos = np.asarray(position, dtype=float)
        if not np.isfinite(pos).all():
            return

        if self._schedule_path_head_actor is None:
            head_mesh = pv.Sphere(radius=NODE_RADIUS * 0.75, center=(0.0, 0.0, 0.0))
            self._schedule_path_head_actor = self.plotter.add_mesh(
                head_mesh,
                color="#ff6b6b",
                name="schedule_path_head",
                reset_camera=False,
            )

        self._schedule_path_head_actor.SetPosition(float(pos[0]), float(pos[1]), float(pos[2]))
        if render:
            self.plotter.render()

    def clear_schedule_path_head(self, render=True):
        """Remove the animated path-head marker if present."""
        if not self.plotter:
            return

        if "schedule_path_head" in self.plotter.renderer.actors:
            self.plotter.remove_actor("schedule_path_head")
        self._schedule_path_head_actor = None
        if render:
            self.plotter.render()

    def draw_schedule_path(self, tiles, up_to_segment=None, max_points=None):
        """
        Draw great-circle arcs connecting scheduled tiles.
        Optionally draw only the first (up_to_segment + 1) segments for animation.
        Or reveal only the first `max_points` points for smooth stroke animation.

        Depth cue: segments closer to the camera are brighter, farther are darker (denoise).
        """
        if not self.plotter:
            return

        path, brightness = self.build_schedule_path_geometry(tiles, up_to_segment=up_to_segment)
        if path is None or len(path) < 2:
            self.clear_schedule_path()
            return
        self.draw_schedule_path_points(path, brightness, max_points=max_points)

    def _slerp_points(self, v1, v2, n=50):
        """Return n points along the great-circle from v1 to v2."""
        v1 = np.asarray(v1, dtype=float)
        v2 = np.asarray(v2, dtype=float)

        # Normalize to unit vectors
        v1 = v1 / np.linalg.norm(v1)
        v2 = v2 / np.linalg.norm(v2)

        # Angle between vectors
        dot = np.clip(np.dot(v1, v2), -1.0, 1.0)
        omega = np.arccos(dot)
        sin_omega = np.sin(omega)

        # If very close or nearly opposite, fall back to normalized lerp
        if np.isclose(omega, 0.0) or np.isclose(sin_omega, 0.0):
            points = np.linspace(v1, v2, n)
            norms = np.linalg.norm(points, axis=1, keepdims=True)
            return points / norms

        # Slerp interpolation
        t = np.linspace(0, 1, n)
        points = (
            np.sin((1 - t) * omega)[:, None] / sin_omega * v1 +
            np.sin(t * omega)[:, None] / sin_omega * v2
        )
        # Normalize to unit sphere
        norms = np.linalg.norm(points, axis=1, keepdims=True)
        return points / norms

    def clear_schedule_path(self, render=True):
        """Remove any existing schedule path lines."""
        if not self.plotter:
            return

        if "schedule_path" in self.plotter.renderer.actors:
            self.plotter.remove_actor("schedule_path")
        self.clear_schedule_path_head(render=False)
        if render:
            self.plotter.render()

    def clear_schedule_labels(self):
        """Remove all scheduled labels."""
        if not self.plotter:
            return

        # Remove the label actor if it exists
        if "scheduled_labels" in self.plotter.renderer.actors:
            self.plotter.remove_actor("scheduled_labels")

        self.plotter.render()

    def show(self):
        """Display the visualization in and interactive window."""
        self.plotter.show(interactive=True)