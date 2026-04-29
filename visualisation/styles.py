"""
Visual styling constants and color schemes for the visualisation.
Defines colors, sizes, and other visual parameters.
"""

# Colors
COLOR_SPHERE_WIREFRAME = 'grey'
COLOR_NODE_UNSELECTED = 'white'
COLOR_NODE_SELECTED = 'red'

# Sizes
SPHERE_RADIUS = 1.0
NODE_RADIUS = 0.01
NODE_POINT_SIZE = 5

# Opacity
NODE_OPACITY_UNSELECTED = 0.8
SPHERE_WIREFRAME_OPACITY = 0.2

# Colormap for probability
PROBABILITY_COLORMAP = 'viridis'

# Scalar bar configuration
# SCALAR_BAR_CONFIG = {
#     'title': 'Probability',
#     'n_labels': 6,
#     'fmt': '%.2f',
#     'vertical': True
# }

SCALAR_BAR_CONFIG = {
    'title': 'Probability',
    'n_labels': 5,
    'fmt': '%.3f',
    'vertical': True,
    'label_font_size': 11,
    'title_font_size': 12,
    'position_x': 0.88,
    'position_y': 0.10,
    'height': 0.75,
    'width': 0.06,
    'shadow': False,
    'interactive': False,
    'background_color': '#0d1117',
    'color': '#e6edf3'
}