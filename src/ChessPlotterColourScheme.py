
import plotnine as gg

class ChessPlotterColourScheme:

    """
    This class is just a container for a number of constants used for consistent plotting.
    """


    # Colours
    white           = "#FFFFFF" 
    black           = "#000000" 
    darkgray        = "#292929"
    gray            = "#666666" 
    lightgray       = "#999999" 
    axis            = "#999999"
    int_orange      = "#FF4F00"
    blue            = "#1e8ef0"
    teal            = "#16e276"
    green           = "#17c903"
    red             = "#dd1616"

    background      = gray
    text            = white
    draw            = gray

    # Colour sets
    colour2 = [blue, int_orange]
    colour3 = [blue, teal, int_orange]
    colour4 = [blue, teal, int_orange, red]
    colour5 = [blue, teal, green, int_orange, red]

    # Text size
    title_size = 20
    axis_size = 16
    legend_title_size = 14
    legend_text_size = 8
    label_size = 10

    # Legend Position
    legend_position = (0.8, 0.90)

    # Legend labels
    legend_result = ["Win", "Draw", "Loss"]
    legend_colour = ["Black", "White"]

    # Axis Limits
    elo_limits = (-150, 150)

    # Blank element
    blank = gg.element_blank()

    # Opacity
    alpha = 0.3

    # Figure size
    figure_size = (20, 10)
