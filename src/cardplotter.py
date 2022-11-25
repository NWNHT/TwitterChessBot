import numpy as np
import pandas as pd
import patchworklib as pw
import plotnine as gg

import re
from typing import Optional

from DBConn import DBConn
from PlotnineElements import PlotnineElements as pe, blank
from ChessPlotterColourScheme import ChessPlotterColourScheme as cpcs


class CardPlotter:

    def __init__(self, db: DBConn, fig_size: tuple=(6, 2)):
        # This assumes that all positions are already present and evaluated
        self.db = db
        self.game_id = None
        self.fig_size = fig_size
        self.x_limit = None
        self.time_control = None
        self.time_plot_break = 60
    
    def gen_card(self, game_id: int, filepath: str=""):
        """
        Generate all of the plots and the card.
        This assumes that the game_id exists in the database and has been fully evaluated.
        """

        self.game_id = game_id

        # Generate all of the sections
        p3 = pw.load_ggplot(self.gen_eval_plot(), figsize=(8, 2))
        p4 = pw.load_ggplot(self.gen_time_plot(), figsize=(8, 2))
        p5 = pw.load_ggplot(self.gen_loss_plot(), figsize=(8, 2))
        p1 = pw.load_ggplot(self.gen_title(), figsize=(6, 1.25))
        p2 = pw.load_ggplot(self.gen_stats(), figsize=(6, 1.25))

        # Combine the plots
        p = p1/p2/p3/p4/p5

        if filepath == "":
            filepath = "./../cards/"
        try:
            filename = filepath + f"{self.game_id}"
            p.savefig(fname=filename)
            print("Saved card")
        except Exception as e:
            print(f"Error saving card: {e}")
            quit()
        
        return filename + '.png'
    
    def gen_eval_plot(self) -> gg.ggplot:
        """
        Generate evaluation and material plot
        """

        # TODO: Might have to adjust the x axis limits to shorten by a single move
        # Request data from database
        try:
            resp = self.db.execute_query(eval_material_query, (self.game_id,))
        except Exception as e:
            print(f"Error requesting evaluation data: {e}")
            quit()
        
        # Create database
        df = pd.DataFrame(resp.fetchall(), columns=['ply_num', 'eval', 'position'])

        # Additional column for the ribbon, converting from centipawns to pawns, converting fen to material balance
        df['zero'] = 0
        df['eval'] = df['eval'] / 100
        df['eval'] = df['eval'].fillna(method='ffill')
        df['eval'] = df['eval'].apply(self.eval_boundary)
        df['material'] = df.position.apply(self.fen_to_material)
        df['material'] = df.material.apply(self.eval_boundary)
        df['eval_shift'] = df['eval'].shift(-1)

        self.x_limit = df.ply_num.max()

        # Create plot
        try:
            g = (gg.ggplot(df[:-1], gg.aes(x='ply_num'))
                    + gg.geom_ribbon(gg.aes(ymin='zero', ymax='eval'), colour=cpcs.int_orange, size=0, alpha=cpcs.alpha + 0.2)
                    + gg.geom_line(gg.aes(y='material'), size=1.5, colour=cpcs.int_orange)
                    + gg.geom_line(gg.aes(y='eval', colour='eval_shift'), size=2)
                    + gg.geom_label(gg.aes(x=(self.x_limit - 1)*0.02 + 1, y=-5.75), ha='left', size=16, label='Material', colour=cpcs.black, fill=cpcs.int_orange)
                    + gg.geom_label(gg.aes(x=(self.x_limit - 1)*0.02 + 1, y=-8.75), ha='left', size=16, label='Evaluation', colour=cpcs.black, fill=cpcs.white)

                    + gg.scale_x_continuous(limits=(1, self.x_limit), expand=(0, 0), breaks=lambda x: range(0, int(x[1]), 10))
                    + gg.scale_y_continuous(limits=(-10, 10), expand=(0, 0), breaks=range(-10, 12, 2), labels=['-10', '', '-6', '', '-2', '', '2', '', '6', '', '10'])
                    + gg.scale_colour_gradientn(colors=[cpcs.black, cpcs.black, cpcs.white, cpcs.white], limits=(-10, 10), values=[0, 0.4999, 0.5001, 1], guide=False)

                    + pe.text(size=14, colour=cpcs.white)
                    + pe.background_colour(colour=cpcs.background)
                    + pe.remove_grid(minor=True)
                    + pe.remove_ticks(x=True, y=True)

                    + gg.ggtitle("Evaluation and Material Balance")
                    + gg.theme(figure_size=self.fig_size)
                    + gg.theme(axis_title_x=gg.element_blank())
                    + gg.ylab('[Pawn]')
                    + gg.theme(axis_text_x=blank)
                    + gg.theme(panel_grid_major=gg.element_line(size=1))
                    )

        except Exception as e:
            print(f"Error generating evaluation plot: {e}")
            quit()
                
        return g

    def gen_time_plot(self):
        """
        Generate time balance plot
        """

        # TODO: Fix the axis limits, possibly implement some sort of variable for the time control of the game
        # Request data from database
        try:
            resp = self.db.execute_query(time_balance_query, (self.game_id, self.game_id))
        except Exception as e:
            print(f"Error requesting time data: {e}")
            quit()
        
        # Create database
        df = pd.DataFrame(resp.fetchall(), columns=['move_num', 'white_clock', 'black_clock', 'clock_diff'])

        # Add zero column for ribbon
        df['zero'] = 0

        # Define limits for plot
        bottom_limit = int(- df.clock_diff.abs().max() // self.time_plot_break * self.time_plot_break)
        top_limit = int(df.clock_diff.abs().max() // self.time_plot_break * self.time_plot_break + self.time_plot_break * 1)

        # Set this for use in the title item
        self.time_control = df.white_clock.iloc[0]

        # Create plot
        try:
            g = (gg.ggplot(df, gg.aes(x='move_num'))
                    + gg.geom_ribbon(gg.aes(ymin='zero', ymax='clock_diff'), size=0, alpha=cpcs.alpha + 0.2)
                    + gg.geom_line(gg.aes(y='clock_diff'), colour=cpcs.int_orange, size=2)
                    + gg.theme(figure_size=self.fig_size)
                    + gg.geom_label(gg.aes(x=(self.x_limit - 1)*0.02 + 1, y=bottom_limit * 0.875), ha='left', size=16, label='Black Time Advantage', colour=cpcs.black, fill=cpcs.white)
                    + gg.geom_label(gg.aes(x=(self.x_limit - 1)*0.02 + 1, y=top_limit * 0.875), ha='left', size=16, label='White Time Advantage', colour=cpcs.black, fill=cpcs.white)
                    # + gg.geom_label(gg.aes(y='clock_diff', label='move_num'))

                    + gg.scale_colour_manual(values=cpcs.colour2)
                    + gg.scale_x_continuous(limits=(1, self.x_limit), expand=(0, 0), breaks=lambda x: range(0, int(x[1]), 10))
                    + gg.scale_y_continuous(limits=(bottom_limit, top_limit), expand=(0, 0), breaks=lambda x: range(bottom_limit, top_limit + self.time_plot_break, 60))

                    + pe.text(size=14, colour=cpcs.white)
                    + pe.background_colour(colour=cpcs.background)
                    + pe.remove_grid(minor=True)
                    + pe.remove_ticks(x=True, y=True)

                    + gg.ggtitle("Time Advantage")
                    + gg.theme(figure_size=self.fig_size)
                    + gg.theme(axis_title_x=gg.element_blank())
                    + gg.ylab('[Second]')
                    + gg.theme(axis_text_x=blank)
                    )

        except Exception as e:
            print(f"Error generated while plotting time balance: {e}")
            quit()
        
        return g

    def gen_loss_plot(self):
        """
        Generate loss plot
        """

        # Request data from database
        try:
            resp = self.db.execute_query(eval_loss_query, (self.game_id,))
        except Exception as e:
            print(f"Error requesting time data: {e}")
            quit()
        
        # Create database
        df = pd.DataFrame(resp.fetchall(), columns=['move_num', 'colour', 'eval_diff'])

        # Convert centipawns to pawns, limit to +/- 10
        df['eval_diff'] = df['eval_diff'] / 100
        df['eval_diff'] = df['eval_diff'].apply(self.eval_boundary)
        # df.loc[df.eval_diff > 10, 'eval_diff'] = 10
        # df.loc[df.eval_diff < -10, 'eval_diff'] = -10

        try:
            g = (gg.ggplot(df, gg.aes(x='move_num', y='eval_diff', colour='colour')) 
                    + gg.geom_line(size=2)
                    # + gg.geom_label(gg.aes(label='move_num'))

                    + gg.theme(figure_size=self.fig_size)
                    
                    # + gg.scale_colour_manual(values=cpcs.colour2, guide=False)
                    + gg.scale_colour_manual(values=[cpcs.black, cpcs.white], guide=False)
                    + gg.scale_x_continuous(limits=(1, self.x_limit), expand=(0, 0), breaks=lambda x: range(0, int(x[1]), 10))
                    + gg.scale_y_continuous(limits=(-10, 10), expand=(0, 0), breaks=range(-10, 12, 2), labels=['-10', '', '-6', '', '-2', '', '2', '', '6', '', '10'])
                    + gg.geom_label(gg.aes(x=(self.x_limit - 1)*0.02 + 1, y=-8.75), ha='left', size=16, label='White Eval Loss', colour=cpcs.black, fill=cpcs.white)
                    + gg.geom_label(gg.aes(x=(self.x_limit - 1)*0.02 + 1, y=8.75), ha='left', size=16, label='Black Eval Loss', colour=cpcs.white, fill=cpcs.black)

                    + pe.text(size=14, colour=cpcs.white)
                    + pe.background_colour(colour=cpcs.background)
                    + pe.remove_grid(minor=True)
                    + pe.remove_ticks(x=True, y=True)

                    + gg.ggtitle("Evaluation Loss by Move")
                    + gg.xlab("[Move]")
                    + gg.theme(figure_size=self.fig_size)
                    + gg.ylab('[Pawn]')
                    )

        except Exception as e:
            print(f"Error while generating loss plot: {e}")
            quit()
        
        return g

    def gen_loss_hist(self):
        """
        Generate loss histograms
        """

        # Request data from database
        try:
            resp = self.db.execute_query(hist_query, (self.game_id,))
        except Exception as e:
            print(f"Error requesting histogram data: {e}")
            quit()
        
        # Create database
        df = pd.DataFrame(resp.fetchall(), columns=['move_num', 'colour', 'eval_diff'])

        # Convert centipawns to pawns, limit to +/- 10
        df['eval_diff'] = df['eval_diff'] / 100
        df['eval_diff'] = df['eval_diff'].apply(self.eval_boundary)
        # df.loc[df.eval_diff > 10, 'eval_diff'] = 10
        # df.loc[df.eval_diff < -10, 'eval_diff'] = -10

        # Generate Plot
        try:
            g = (gg.ggplot(df, gg.aes(x='eval_diff', fill='colour')) 
                    + gg.geom_histogram(colour=cpcs.white, binwidth=0.5, show_legend=False)
                    + gg.facet_grid('. ~ colour')

                    + gg.theme(figure_size=self.fig_size)
                    
                    + gg.scale_colour_manual(values=cpcs.colour2, guide=False)
                    + gg.scale_x_continuous(limits=(-0.5, 10), expand=(0, 0), labels=[0, 2, 4, 6, 8])

                    + pe.text(size=14, colour=cpcs.white)
                    + pe.background_colour(colour=cpcs.background)
                    + pe.remove_grid(minor=True)
                    + pe.remove_ticks(x=True, y=True)

                    + gg.theme(axis_title_x=gg.element_blank())
                    + gg.theme(strip_background=gg.element_rect(colour=cpcs.background))
                    + gg.ylab('[Pawn]')
                    + gg.theme(legend_text=blank)
                    )

        except Exception as e:
            print(f"Error while generating loss plot: {e}")
            quit()
        
        return g
    
    def gen_stats(self):
        """
        Generate the statistics for the card
        """

        # Request statistic data
        try:
            move_loss_stat = self.db.execute_query(move_loss_stat_query, (self.game_id,))
            move_loss_stat = move_loss_stat.fetchall()

            avg_move_rank_stat = self.db.execute_query(avg_move_rank_stat_query, (self.game_id,))
            avg_move_rank_stat = avg_move_rank_stat.fetchall()

            move_rank_count_stat = self.db.execute_query(move_rank_count_stat_query, (self.game_id,))
            move_rank_count_stat = move_rank_count_stat.fetchall()
        except Exception as e:
            print(f"Error requesting statistics data: {e}")
            quit()
        
        # Create dataframe from requested data
        df = pd.DataFrame(move_loss_stat, columns=['colour', 'Avg. Move Loss', 'Total Move Loss'])

        df['Avg. Move Rank'] = [avg_move_rank_stat[0][1], avg_move_rank_stat[1][1]]

        if len(move_rank_count_stat) < 4: # If the player didn't make any best moves, or second best moves, ... then fill in the gaps
            for i, v in enumerate([1, 2, 3, 5]):
                if move_rank_count_stat[i][0] != v:
                    move_rank_count_stat.insert(i, (v, 0, 0))
        move_rank_count_stat = [[x[i] for x in move_rank_count_stat] for i in range(1, 3)]
        df = pd.concat([df,
                        pd.DataFrame(move_rank_count_stat, columns=['Best Move', 'Second Best Move', 'Third Best Move', 'Other Moves'])
                        ], axis=1)

        # Convert centipawn to pawn
        df['Total Move Loss'] = df['Total Move Loss'] / 100
        df['Avg. Move Loss'] = df['Avg. Move Loss'] / 100

        # Melt dataframe
        df_melt = pd.melt(df, id_vars=['colour'])
        df_melt['variable'] = pd.Categorical(df_melt['variable'], categories=['Other Moves', 'Third Best Move', 'Second Best Move', 'Best Move', 'Avg. Move Rank', 'Avg. Move Loss', 'Total Move Loss'], ordered=True)

        # Create label column and make white values negative for plotting
        df_melt['label'] = df_melt.value.apply(lambda x: f"{x:.0f}" if abs(x - round(x, 0)) < 0.001 else f"{x:.1f}")
        df_melt['value'] = df_melt.apply(lambda x: x['value'] if x['colour'] == 'Black' else -x['value'], axis=1)

        # Create plot
        g = (gg.ggplot(df_melt, gg.aes(x='variable', y='value', fill='colour', label='label'))
                    + gg.geom_bar(stat='identity', colour=cpcs.lightgray)
                    + gg.geom_label(gg.aes(y='1.1*max(abs(value)) * value/abs(value)', colour='colour'))
                    + gg.coord_flip()
                    + gg.theme(figure_size=self.fig_size)
                    
                    # + gg.scale_fill_manual(values=cpcs.colour2, guide=False)
                    + gg.scale_fill_manual(values=[cpcs.black, cpcs.white], guide=False)
                    + gg.scale_colour_manual(values=[cpcs.white, cpcs.black], guide=False)
                    + gg.scale_y_continuous(limits=(-df_melt.value.abs().max()*1.2, df_melt.value.abs().max()*1.2), expand=(0, 0))

                    + pe.text(size=14, colour=cpcs.white)
                    + pe.background_colour(colour=cpcs.background)
                    + pe.remove_grid(minor=True, major=True)
                    + pe.remove_ticks(x=True, y=True)

                    + gg.theme(axis_title_x=blank, axis_title_y=blank, axis_text_x=blank, axis_text_y=gg.element_text(size=10))
                    + gg.theme(legend_position='none'))

        return g
    
    def gen_title(self):
        """
        Generate the titles for the plot
        """

        # Request data
        try:
            summary = self.db.execute_query(summary_query, (self.game_id,))
            summary = summary.fetchall()[0]
        except Exception as e:
            print(f"Error requesting histogram data: {e}")
            quit()
        
        names = f"{summary[0]} vs. {summary[1]}"
        game_date = summary[3][:10]
        result = summary[2]
        time_control = f"Time: {int(self.time_control // 60)} + {int(self.time_control % 60)}"

        g = (gg.ggplot()
                + gg.geom_text(gg.aes(x=0, y=18), size=36, colour=cpcs.white, label=names)
                + gg.geom_text(gg.aes(x=0, y=15.2), size=16, colour=cpcs.white, label=game_date)
                + gg.geom_text(gg.aes(x=0, y=13.5), size=16, colour=cpcs.white, label=time_control)
                + gg.geom_text(gg.aes(x=0, y=11), size=36, colour=cpcs.white, label=result)

                + gg.scale_y_continuous(limits=(10, 19.5))

                + pe.text(size=14, colour=cpcs.white)
                + pe.background_colour(colour=cpcs.background)
                + pe.remove_grid(minor=True, major=True)
                + pe.remove_ticks(x=True, y=True)

                + gg.theme(panel_border=blank)
                + gg.theme(axis_title_x=blank, axis_title_y=blank, axis_text_x=blank, axis_text_y=blank)
                + gg.theme(legend_position='none')
                )
        
        return g

    @staticmethod
    def fen_to_material(fen: str):
        """
        Return the material balance of a position
        """

        pieces = {'P': 1, 'p': -1, 'B': 3, 'b': -3, 'N': 3, 'n':-3, 'R': 5, 'r': -5, 'Q': 9, 'q': -9}
        vals = re.sub('[/0-9Kk]', '', fen.split(' ')[0])
        total = 0
        for val in vals:
            total += pieces[val]
        return total

    @staticmethod
    def eval_boundary(val: float):
        if val > 10:
            return 10
        elif val < -10:
            return -10
        else:
            return val


# Material query
eval_material_query = """
SELECT CASE WHEN p.colour = 'b' THEN gm.move_num
            WHEN p.colour = 'w' THEN gm.move_num + 0.5 END as ply_num,
       CASE WHEN p.first_move_eval_type = 'mate' THEN 1000 * (p.first_move_eval)/ABS(p.first_move_eval)
            ELSE p.first_move_eval END as eval,
       p.fen as position
FROM Game       g
JOIN GameMove   gm  ON g.game_id = gm.game_id
JOIN Move       m   ON gm.move_id = m.move_id
JOIN Position   p   ON m.position_id = p.position_id
WHERE g.game_id = ?
ORDER BY move_num
"""

# Time balance query
time_balance_query = """
SELECT W.move_num,
       W.clock,
       B.clock,
       W.clock - B.clock AS clock_diff
FROM (SELECT *
      FROM Game g
      JOIN GameMove gm
      ON g.game_id = gm.game_id
      JOIN Move m
      ON gm.move_id = m.move_id
      JOIN Position p
      ON m.position_id = p.position_id
      WHERE g.game_id = ?
        AND p.colour = 'b') W
      JOIN (SELECT gm.move_num, 
                   clock
            FROM Game g
            JOIN GameMove gm
            ON g.game_id = gm.game_id
            JOIN Move m
            ON gm.move_id = m.move_id
            JOIN Position p
            ON m.position_id = p.position_id
            WHERE g.game_id = ?
            AND p.colour = 'w') B
ON B.move_num = W.move_num
"""

# Eval loss query
eval_loss_query = """	
SELECT move_num,
       colour,
       eval - LAG(eval, 1) OVER (PARTITION BY game_id ORDER BY ply_num) AS diff
FROM (SELECT g.game_id,
             p.position_id, 
             CASE WHEN p.colour = 'w' THEN 'Black'
                  WHEN p.colour = 'b' THEN 'White' END AS colour,
             gm.move_num,
             CASE WHEN p.colour = 'b' THEN 2 * gm.move_num - 1
                  WHEN p.colour = 'w' THEN 2 * gm.move_num END as ply_num,
			 CASE WHEN p.first_move_eval_type = 'mate' THEN 10000 * (p.first_move_eval)/ABS(p.first_move_eval)
                  ELSE p.first_move_eval END as eval
      FROM Game g
      JOIN GameMove gm
      ON g.game_id = gm.game_id
      JOIN Move m
      ON gm.move_id = m.move_id
      JOIN Position p
      ON m.position_id = p.position_id
      WHERE g.game_id = ?) sub
ORDER BY ply_num, 3 DESC
"""

# Histogram query
hist_query = """
SELECT  move_num,
        colour,
        ABS(eval - LAG(eval, 1) OVER (PARTITION BY game_id ORDER BY ply_num)) AS diff
FROM (SELECT g.game_id,
             p.position_id, 
             CASE WHEN p.colour = 'w' THEN 'Black'
                  WHEN p.colour = 'b' THEN 'White' END AS colour,
             gm.move_num,
             CASE WHEN p.colour = 'b' THEN 2 * gm.move_num - 1
                  WHEN p.colour = 'w' THEN 2 * gm.move_num END as ply_num,
             CASE WHEN p.first_move_eval_type = 'mate' THEN 1000 * (p.first_move_eval)/ABS(p.first_move_eval)
                  ELSE p.first_move_eval END as eval
      FROM Game g
      JOIN GameMove gm
      ON g.game_id = gm.game_id
      JOIN Move m
      ON gm.move_id = m.move_id
      JOIN Position p
      ON m.position_id = p.position_id
      WHERE g.game_id = ?) sub
ORDER BY ply_num
"""

# Average and total move loss query
move_loss_stat_query = """
SELECT move_colour,
       ABS(AVG(diff)) as avg_eval_loss,
       ABS(SUM(diff)) as total_eval_loss
FROM (SELECT move_colour,
             eval - LAG(eval, 1) OVER (PARTITION BY game_id ORDER BY ply_num) AS diff
      FROM (SELECT g.game_id,
                   p.position_id, 
                   CASE WHEN p.colour = 'w' THEN 'Black'
                        WHEN p.colour = 'b' THEN 'White' END AS move_colour,
                   gm.move_num,
                   CASE WHEN p.colour = 'b' THEN 2 * gm.move_num - 1
                        WHEN p.colour = 'w' THEN 2 * gm.move_num END as ply_num,
                   CASE WHEN p.first_move_eval_type = 'mate' THEN 1000 * (p.first_move_eval)/ABS(p.first_move_eval)
                        ELSE p.first_move_eval END as eval
            FROM Game g
            JOIN GameMove gm
            ON g.game_id = gm.game_id
            JOIN Move m
            ON gm.move_id = m.move_id
            JOIN Position p
            ON m.position_id = p.position_id
            WHERE g.game_id = ?) sub
      ) sub
GROUP BY move_colour
"""

# Move rank query
avg_move_rank_stat_query = """
SELECT move_colour,
       AVG(move_rank) AS average_move_rank
FROM (SELECT gm.move_num,
             p.colour,
             CASE WHEN p.colour = 'w' THEN 'Black'
                  WHEN p.colour = 'b' THEN 'White' END AS move_colour,
             CASE m.move_uci WHEN LAG(p.first_move, 1) OVER (PARTITION BY g.game_id ORDER BY gm.move_num) THEN 1
                  WHEN  LAG(p.second_move, 1) OVER (PARTITION BY g.game_id ORDER BY gm.move_num) THEN 2
                  WHEN  LAG(p.third_move, 1) OVER (PARTITION BY g.game_id ORDER BY gm.move_num) THEN 3
                  ELSE 5 END AS move_rank,
             m.move_uci,
             CASE WHEN p.first_move_eval_type = 'mate' THEN 1000 * (p.first_move_eval)/ABS(p.first_move_eval)
                  ELSE p.first_move_eval END as eval
      FROM Game g
      JOIN GameMove gm
      ON g.game_id = gm.game_id
      JOIN Move m
      ON gm.move_id = m.move_id
      JOIN Position p
      ON m.position_id = p.position_id
      WHERE g.game_id = ?
      ORDER BY move_num) sub
GROUP BY move_colour
ORDER BY move_colour
"""

# Move rank count query
move_rank_count_stat_query = """
SELECT move_rank,
       COUNT(CASE move_colour WHEN 'Black' THEN 1 ELSE NULL END) AS Black,
       COUNT(CASE move_colour WHEN 'White' THEN 1 ELSE NULL END) AS White
FROM (SELECT gm.move_num,
             p.colour,
             CASE WHEN p.colour = 'w' THEN 'Black'
                  WHEN p.colour = 'b' THEN 'White' END AS move_colour,
             CASE m.move_uci WHEN LAG(p.first_move, 1) OVER (PARTITION BY g.game_id ORDER BY gm.move_num) THEN 1
                  WHEN LAG(p.second_move, 1) OVER (PARTITION BY g.game_id ORDER BY gm.move_num) THEN 2
                  WHEN LAG(p.third_move, 1) OVER (PARTITION BY g.game_id ORDER BY gm.move_num) THEN 3
                  ELSE 5 END AS move_rank,
             m.move_uci,
             CASE WHEN p.first_move_eval_type = 'mate' THEN 1000 * (p.first_move_eval)/ABS(p.first_move_eval)
                  ELSE p.first_move_eval END as eval
      FROM Game g
      JOIN GameMove gm
      ON g.game_id = gm.game_id
      JOIN Move m
      ON gm.move_id = m.move_id
      JOIN Position p
      ON m.position_id = p.position_id
      WHERE g.game_id = ?
      ORDER BY move_num) sub
GROUP BY move_rank
ORDER BY move_rank
"""

# Title query
summary_query = """
SELECT u1.username AS White,
       u2.username AS Black,
       g.result AS Result,
       g.occurred_at as Date
FROM Game g
JOIN User u1
ON g.white = u1.user_id
JOIN User u2
ON g.black = u2.user_id
WHERE game_id = ?
"""
