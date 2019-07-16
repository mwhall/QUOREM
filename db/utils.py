import plotly.graph_objs as go
from plotly.io._html import to_html
from django.db.models import Count, Avg, Q
from . import models

def barchart_html(agg, inv, model, meta):
    Operation = None
    title = None
    type = None
    metaType = None

    investigation = models.Investigation.objects.get(pk=inv)
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
        return to_html(figure, full_html=False), {'agg':title,
                                                  'inv': investigation.name,
                                                  'type':model_choice,
                                                  'meta':meta}
    return None
