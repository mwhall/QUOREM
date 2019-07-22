import plotly.graph_objects as go
from plotly.io._html import to_html
from django.db.models import Count, Avg, Q
from . import models

#Code for barchart from plot_aggregate
def barchart_html(agg, inv, model, meta):
    Operation = None
    title = None
    type = None
    metaType = None

    investigation = models.Investigation.objects.get(pk=inv[0])
    #Assign aggregate operation
    if agg == '1':
        Operation = Count
        title = "Count"
    elif agg == '2':
        Operation = Avg
        title = "Average"
    #Assign Model type
    if model == '1':
        type = models.Sample
        model_choice = "Sample"
        metaType = models.SampleMetadata
    elif model == '2':
        type = models.BiologicalReplicate
        model_choice = "Biological Replicate"
        metaType = models.BiologicalReplicateMetadata
    #using this conditional will allow later additions to this method.
    if metaType:
        qs = metaType.objects.filter(sample__in=models.Sample.objects.filter(investigation=inv)).filter(key=meta).values('value').order_by(
            'value').annotate(agg=Operation('value'))
        #plotly plot
        x = [s['value'] for s in qs]
        y = [s['agg'] for s in qs]

        data = [go.Bar(
            x=x,
            y=y,
            text=y,
            textposition= 'auto',
            marker=dict(
                color='rgb(158,202,225)',
                line=dict(
                    color='rgb(8,48,107)',
                    width=1.5),
            ),
            opacity=0.75,
        )]

        layout = go.Layout(title=(title + " by  " + meta),
                           xaxis={'title': meta},
                           yaxis={'title': title})

        figure = go.Figure(data=data, layout=layout)
        if figure:
            print("a figure was made")
        else:
            print("something is wrong")
        return to_html(figure, full_html=False), {'agg':title,
                                                  'inv': investigation.name,
                                                  'type':model_choice,
                                                  'meta':meta}
    return None

#Code for trendline/scatterplot
def trendchart_html(invs, x_val, x_val_category, y_val, y_val_category, operation):
    #To save code, use a dict that maps numerical field vals to django model
    cat_map = {'1': (models.Sample, models.SampleMetadata, 'sample__in'),
               '2': (models.BiologicalReplicate, models.BiologicalReplicateMetadata, 'biological_replicate__in'),
              }
    op_map = {'1': 'markers', '2': 'lines+markers'}

    x = None
    y = None
    xqs = None
    yqs = None

    x_type, x_subtype, x_search = cat_map[x_val_category]
    y_type, y_subtype, y_search = cat_map[y_val_category]

    #For now,there are no cases that don't have subtypes. Later, however, we might
    #expect those cases and will make the code execute condiitionally.


    #TODO: abstract out the terms'key' and 'value' from this query.
    if x_type is models.Sample:
        xqs = x_subtype.objects.filter(**{x_search: x_type.objects.filter(
                                    investigation__in=invs)}).filter(
                                    key=x_val).values('value').order_by('value')

    elif x_type is models.BiologicalReplicate:
        xqs = x_subtype.objects.filter(**{x_search: x_type.objects.filter(
                                    sample__in=models.Sample.objects.filter(
                                    investigation__in=invs))}).filter(
                                    key=x_val).values('value').order_by('value')

    if y_type is models.Sample:
        yqs = y_subtype.objects.filter(**{y_search: y_type.objects.filter(
                                    investigation__in=invs)}).filter(
                                    key=y_val).values('value').order_by('value')

    elif y_type is models.BiologicalReplicate:
        yqs = y_subtype.objects.filter(**{y_search: y_type.objects.filter(
                                    sample__in=models.Sample.objects.filter(
                                    investigation__in=invs))}).filter(
                                    key=y_val).values('value').order_by('value')

    x = [s['value'] for s in xqs]
    y = [s['value'] for s in yqs]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y,
                            mode=op_map[operation],
                            marker_color='rgba(152, 0, 0,0.9)'))
    layout = go.Layout(title=x_val + " vs "  + y_val,
                    xaxis={'title':x_val},
                    yaxis={'title':y_val})
    fig.layout = layout
    return to_html(fig, full_html=False)
