import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.offline as plt
import plotly.express as px
from itertools import cycle
import ete3
import skbio
from .models import *



def pcoa_plot(countmatrix_pk, measure='braycurtis', metadata_colour=None, plot_height=750, three_dimensional=False):
    count_matrix_result = Result.objects.get(pk=countmatrix_pk)
    count_matrix = count_matrix_result.values.instance_of(Matrix).first().data.get().get_value()
    count_matrix = count_matrix.loc[:, (count_matrix != 0).any(axis=0)]
    pcoa = skbio.stats.ordination.pcoa(skbio.diversity.beta_diversity(measure, count_matrix.T))
    pcoa.samples.index = count_matrix.T.index
    plot_kwargs = {}
    if metadata_colour != None and metadata_colour != '':
        try:
            metadata_colour = int(metadata_colour)
            metadata_name = DataSignature.objects.get(pk=metadata_colour).name
        except:
            metadata_name = metadata_colour
        sample_df = Sample.dataframe(Sample.objects.filter(name__in=pcoa.samples.index.tolist()),
                                     value_names=[metadata_name])
        not_in_df = [x for x in pcoa.samples.index if x not in sample_df.index]
        md = pd.DataFrame({metadata_name:{x:"No Metadata Found" for x in not_in_df}})
        sample_df = sample_df.append(md)
        plot_kwargs['color'] = sample_df[metadata_name][pcoa.samples.index]
    relative_x_axis = (pcoa.proportion_explained['PC1']/pcoa.proportion_explained['PC2'])
    if three_dimensional:
        fig = px.scatter_3d(pcoa.samples, x="PC1", y="PC2", z="PC3",
                            hover_name=pcoa.samples.index.tolist(), height=plot_height, **plot_kwargs)
        fig.update_traces(marker={'size': 2})
        fig.update_layout(title={
                                  'text': "PCoA Plot (Measure: %s)" % (measure,),
                                  'y':0.9,
                                  'x':0.5,
                                  'xanchor': 'center',
                                  'yanchor': 'top'}, 
               scene=dict(xaxis_title="PC1 (%3.2f%%)" % (pcoa.proportion_explained['PC1']*100,),
                          yaxis_title="PC2 (%3.2f%%)" % (pcoa.proportion_explained['PC2']*100,),
                          zaxis_title="PC3 (%3.2f%%)" % (pcoa.proportion_explained['PC3']*100,)))

    else:
        fig = px.scatter(pcoa.samples, x="PC1", y="PC2",hover_name=pcoa.samples.index.tolist(), height=plot_height, width=plot_height*relative_x_axis, **plot_kwargs)
        fig.update_layout(xaxis_title="PC1 (%3.2f%%)" % (pcoa.proportion_explained['PC1']*100,),
                          yaxis_title="PC2 (%3.2f%%)" % (pcoa.proportion_explained['PC2']*100,))
    return fig

def count_table_tax_plot(taxonomy_pk, countmatrix_pk, plot_type='bar', plot_height=1000, level='full', n_taxa=10, normalize_method='proportion', metadata_collapse=None, metadata_sort=None, label_bars=False, remove_empty_samples=True):
    collapsed_df = collapsed_table(taxonomy_pk, countmatrix_pk, level, normalize_method, metadata_collapse, metadata_sort)
    # Remove empty columns
    if remove_empty_samples:
        collapsed_df = collapsed_df.loc[:, (collapsed_df != 0).any(axis=0)]
    # Sort table by taxon sum
    collapsed_df = collapsed_df.assign(sum=collapsed_df.sum(axis=1)).sort_values(by='sum', ascending=False).drop(columns='sum')
    # Take the top n_taxa
    collapsed_df = collapsed_df.iloc[0:n_taxa]
    # Plot the transpose with Plotly Express
    plot_kwargs = {}
    if plot_type == 'bar':
        if label_bars:
            plot_kwargs['text']='taxonomy'
        fig=px.bar(collapsed_df.T, **plot_kwargs)
        fig.update_layout(height=plot_height,
                      yaxis_title=normalize_method.capitalize(),
                      xaxis_title='Samples',
                      legend_title='Taxonomic Classification',
                      plot_bgcolor='rgba(0,0,0,0)')
    elif plot_type == 'heatmap':
        fig=px.imshow(collapsed_df,aspect='auto')
        fig.update_layout(height=plot_height,
                          yaxis_nticks=n_taxa, 
                          xaxis_title='',
                          yaxis_title='Taxonomy',
                          plot_bgcolor='rgba(0,0,0,0)')
    elif plot_type == 'area':
        fig=px.area(collapsed_df.T)
        fig.update_layout(height=plot_height,
                          plot_bgcolor='rgba(0,0,0,0)')
    elif plot_type == 'box':
        fig=px.box(collapsed_df.T)
        fig.update_layout(height=plot_height,
                          plot_bgcolor='rgba(0,0,0,0)')
    elif plot_type == 'violin':
        fig=px.violin(collapsed_df.T)
        fig.update_layout(height=plot_height,
                          plot_bgcolor='rgba(0,0,0,0)')

    return fig

def tree_plot(tree_pk, feature_names=[], show_names=False, return_ete=False):
    tree_result = Result.objects.get(pk=tree_pk)
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
    tree = tree.get_common_ancestor(feature_names)
    svg = tree.render("%%return", tree_style=ts)[0].replace("b'","'").strip("'").replace("\\n","").replace("\\'","")
    svg = svg.replace("<svg ", "<svg class=\"img-fluid\" ")
    return svg

#Reuses a lot of code from taxabar plot for now
def tax_correlation_plot(taxonomy_pk, countmatrix_pk, samples=None, level=3, relative=True ):
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

    sample_df = pd.DataFrame({'sample':sample_names})

    for tax, merge in tax_merge.items():
        y=matrix[merge][:,sample_pks].sum(axis=0).tolist()[0],
        sample_df[tax] = y[0]

    #retrieve sample values. Find pearson correlation of sample vals to taxa. plot heatmap
    sqs = Sample.objects.filter(name__in=sample_names)
    val_names = list(set([v.signature.get().name for v in Value.objects.non_polymorphic().filter(samples__in=sqs)]))
    val_index = {name:i for i, name in enumerate(val_names)}

    data = []
    for s in sqs:
        s_vals = [np.nan] * len(val_names)
        for val in s.values.non_polymorphic().filter(signature__name__in=val_names):
            s_vals[val_index[val.signature.get().name]] = val.data.get().value
        data.append([s.name] + s_vals)


    df = pd.DataFrame(data=data, columns=["sample"]+val_names)
    no_file_info = [col for col in df.columns if not "file" in col and not "table" in col]
    print(no_file_info)
    df = df[no_file_info]
    df = df.set_index('sample')

    joined = sample_df.join(df, on='sample')
    pearson = joined.corr().filter(no_file_info)

    fig = go.Figure(data=go.Heatmap(
        z=pearson.values,
        x=pearson.columns,
        y=list(pearson.index),
        hoverongaps=False
    ))


    return plt.plot(fig, output_type="div")

def collapsed_table(taxonomy_pk, countmatrix_pk, level="full", normalize_method="none", metadata_collapse=None, metadata_sort=None):
    linnean_levels = {y: x for x,y in enumerate(["kingdom", "phylum", "class", "order", "family", "genus", "species"])}
    linnean_levels['domain'] = 1
    try:
        level = int(level)
        level = level - 1 #0-based indexing on array
    except:
        pass
    if type(level) != int:
        level = level.lower()
        if level in linnean_levels:
            level = linnean_levels[level]
        else:
            if level != "full":
                raise ValueError("Unknown level %s" % (level,))
    tax_result = Result.objects.get(pk=taxonomy_pk)
    count_matrix_result = Result.objects.get(pk=countmatrix_pk)
    matrix = count_matrix_result.values.instance_of(Matrix).first().data.get().get_value()
    if metadata_collapse != None and metadata_collapse != '':
        try:
            metadata_collapse = int(metadata_collapse)
            metadata_name = DataSignature.objects.get(pk=metadata_collapse).name
        except:
            metadata_name = metadata_collapse
        sample_df = Sample.dataframe(Sample.objects.filter(name__in=matrix.columns),
                                     value_names=[metadata_name])
        matrix = matrix.groupby(by=sample_df[metadata_name],axis=1).sum()
    assert normalize_method.lower() in ["none", "raw", "counts", "percent", "proportion"], \
        "Normalization method must be one of: none, raw, counts, percent, or proportion"
    if normalize_method.lower() == "proportion":
        matrix = matrix/matrix.sum()
    elif normalize_method.lower() == "percent":
        matrix = matrix/matrix.sum()*100

    tax_df = tax_result.dataframe(value_names=["taxonomic_classification"],
                                  additional_fields=["features__name"])
    tax_df = tax_df.set_index("features__name")
    if level == "full":
        level_df = tax_df['value_data']
    else:
        level_df = tax_df['value_data'].str.split(";",expand=True)[level]
        level_df[level_df.isna()] = "Unclassified at level %s" % (str(level+1),)
    level_df = level_df.astype('category')
    level_df.name = None
    matrix=matrix.melt(ignore_index=False, var_name = "sample", value_name="abundance")
    matrix["taxonomy"] = level_df.loc[matrix.index]
    matrix = matrix.groupby(['sample','taxonomy']).sum().unstack().transpose()
    matrix.reset_index(level=0,drop=True,inplace=True)
    return matrix
