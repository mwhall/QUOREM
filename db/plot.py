import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.offline as plt
import ete3
from .models import *


def tax_bar_plot(taxonomy_pk, countmatrix_pk, samples=None, level=6, relative=True, jupyter=False):
    linnean_levels = {y: x for x,y in enumerate(["kingdom", "phylum", "class", "order", "family", "genus", "species"])}
    if level in linnean_levels:
        level = linnean_levels[level]
    elif type(level) == str:
        level = int(level)
    tax_result = Result.objects.get(pk=taxonomy_pk)
    count_matrix_result = Result.objects.get(pk=countmatrix_pk)
    matrix = count_matrix_result.values.instance_of(Matrix).first().data.get().get_value()
    if relative:
        matrix = matrix/matrix.sum(axis=0)
    else:
        matrix = matrix.todense()
    sample_pks = count_matrix_result.samples.order_by("pk")
    sample_names = count_matrix_result.samples.order_by("pk")
    if samples:
        sample_pks = sample_pks.filter(pk__in=samples)
        sample_names = sample_names.filter(pk__in=samples)
    sample_pks = list(sample_pks.values_list("pk",flat=True))
    sample_names = list(sample_names.values_list("name",flat=True))
    tax_df = tax_result.dataframe(value_names=["taxonomic_classification"],
                                  additional_fields=["features__pk"])
    def format_taxonomy(x):
        if len(x) <= level:
            tax_index = len(x)-1
        else:
            tax_index = level
        while x[tax_index].endswith("__"):
            tax_index -= 1
        if tax_index > 0:
            return "; ".join([x[tax_index-1], x[tax_index]])
        else:
            return x[tax_index]
    tax_df["value_data"] = tax_df["value_data"].str.split("; ").apply(format_taxonomy)
    tax_merge = tax_df.groupby("value_data").apply(lambda x: x['features__pk'].unique())
    data = []
    for tax, merge in tax_merge.items():
        data.append(go.Bar(name=tax,
                           x=sample_names,
                           y=matrix[merge][:,sample_pks].sum(axis=0).tolist()[0],
                           text=tax,
                          hoverinfo='x+text+y'))
    fig = go.Figure(data=data)
    # Change the bar mode
    fig.update_layout(barmode='stack',
                     legend_orientation='h',
                     legend=dict(x=0,y=-1.7),
                     height=750)
    if jupyter:
        return plt.iplot(fig)
    return plt.plot(fig, output_type="div")

def tree_plot(tree_pk, feature_pks=[], show_names=False, return_ete=False):
    tree_result = Result.objects.get(pk=tree_pk)
    if not feature_pks:
        feature_pks = list(tree_result.features.values_list("name", flat=True))
    else:
        feature_pks = list(Feature.objects.filter(pk__in=feature_pks).values_list("name", flat=True))
    newick_str = tree_result.get_value("newick")
    tree = ete3.Tree(newick_str)
    if return_ete:
        return tree
    ts = ete3.TreeStyle()
    ts.show_leaf_name = show_names
    ts.mode = "c"
    ts.root_opening_factor = 0.075
    ts.arc_start = -180 # 0 degrees = 3 o'clock
    ts.arc_span = 360
    tree = tree.get_common_ancestor(feature_pks)
    svg = tree.render("%%return", tree_style=ts)[0].replace("b'","'").strip("'").replace("\\n","").replace("\\'","")
    svg = svg.replace("<svg ", "<svg class=\"img-fluid\" ")
    return svg
