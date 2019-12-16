import plotly.graph_objects as go
from plotly.io._html import to_html
from django.db.models import Count, Avg, Q, F

from .models import *

import pandas as pd

#Code for barchart from plot_aggregate
def barchart_html(agg, inv, model, meta):
    # Use a dict to map query result to necessary query expression.
    #This is based on types defined by models.Value
    print (meta[0])

    mapping = {'str val': 'str__value',
               'float val': 'float__value',}

    Operation = None
    title = None
    v_type = None #value type
    v_raw = None #raw qs of values

    investigations = models.Investigation.objects.filter(pk__in=inv)
    inv_titles = [i.name for i in investigations]
    #Assign aggregate operation
    if agg == '1':
        Operation = Count
        title = "Count"
    elif agg == '2':
        Operation = Avg
        title = "Average"
    elif agg == '3':
        title = 'Stack'
    #Assign Model type
    if model == '1':
        type = models.Sample
        model_choice = "Sample"
#        metaType = models.SampleMetadata
    elif model == '2':
        type = models.Replicate
        model_choice = "Replicate"
#        metaType = models.BiologicalReplicateMetadata

    #create a qs for each investigation. This will allow comparison accorss invs.

    sets = []
    if Operation != None:
        meta = meta[0]
        print(meta)
        for inv in investigations:
            if model_choice=="Sample":
                v_raw = models.Value.objects.filter(samples__in=models.Sample.objects.filter(investigation=inv)).filter(name=meta)
                v_type = v_raw[0].content_type.name
                filter = mapping[v_type]
                print(filter)
                sets.append({'title': inv.name,
                             'data': v_raw.values(filter).order_by(filter).annotate(agg=Operation(filter))
                             })
    #logic for stacked bar chart
    else:
        if model_choice=="Sample":
            vqs = models.Value.objects.filter(name__in=meta).filter(samples__in=models.Sample.objects.filter(investigation__in=investigations))
            sqs = models.Sample.objects.filter(values__in=vqs).distinct()
            v_names = []
            v_dict = {}
            s_set = []
            for sample in sqs:
                s_set.append(sample.name)
                vals = vqs.filter(samples__in=[sample]).distinct()
                for val in vals:
                    if val.name in v_dict.keys():
                        v_dict[val.name].append(val.content_object.value)
                    else:
                        v_names.append(val.name)
                        v_dict[val.name] = [val.content_object.value]

        #    v_names = list(set(v_names))

            #GO for plotly
            data = []
            for name in v_names:
                data.append(go.Bar(name=name, x=s_set, y=v_dict[name]))

            layout= go.Layout(title="Samples with selected values",
                              xaxis={'title': 'Sample Name'},)
            fig = go.Figure(data=data, layout=layout)
            fig.update_layout(barmode='stack')
            return to_html(fig, full_html=False), {'agg': title,
                                                      'inv': inv_titles,
                                                      'type':model_choice,
                                                      'meta':meta}

    #create values for plotly
    graph_values = []
    for qs in sets:
        print(qs)
        graph_values.append(
            {'x': [s[filter] for s in qs['data']],
             'y': [s['agg'] for s in qs['data']],
             'title': qs['title']}
        )

    data = []
    for bar in graph_values:
        data.append(go.Bar(
            x=bar['x'],
            y=bar['y'],
            text=bar['y'],
            textposition = 'auto',
            name=bar['title'],
        ))

    layout = go.Layout(title=(title + " by  " + meta),
                       xaxis={'title': meta},
                       yaxis={'title': title})

    figure = go.Figure(data=data, layout=layout)
    return to_html(figure, full_html=False), {'agg':title,
                                              'inv': inv_titles,
                                              'type':model_choice,
                                              'meta':meta}
    return None

#Code for trendline/scatterplot
def trendchart_html(invs, x_val, x_val_category, y_val, y_val_category, operation):
    """
    #To save code, use a dict that maps numerical field vals to django model
    cat_map = {'1': (models.Sample, models.SampleMetadata, 'sample__in', "Sample"),
               '2': (models.BiologicalReplicate, models.BiologicalReplicateMetadata, 'biological_replicate__in', "Biological Replicate"),
              }
    op_map = {'1': 'markers', '2': 'lines+markers'}

    x = None
    y = None
    xqs = None
    yqs = None

    x_type, x_subtype, x_search, x_cat = cat_map[x_val_category]
    y_type, y_subtype, y_search, y_cat = cat_map[y_val_category]

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
    """

    cat_map = {'1': (models.Sample, 'samples__in', "Sample"),}
    op_map = {'1': 'markers', '2': 'lines+markers'}
    q_map = {'str val': 'str__value',
            'int val': 'int__value',
            'float val': 'float__value',}

    x = None
    y = None
    xqs = None
    yqs = None
    qs = None #for finding same objects in x and y

    x_type, x_search, x_cat = cat_map[x_val_category]
    y_type, y_search, y_cat = cat_map[y_val_category]

    if x_type is models.Sample:
        xqs = models.Value.objects.filter(**{x_search: x_type.objects.filter(
                                    investigation__in=invs)}).filter(
                                    name=x_val)
        xval_type = xqs[0].content_type.name
        x_filt = q_map[xval_type]
        xqs = xqs.order_by(x_filt)
        s_filt = x_filt + "__values"
        qs = x_type.objects.filter(values__in=xqs).order_by(s_filt)

        ### Y options will be dependant on x choice.
        ### only choice for y when x is samples is also samples for now.

        #by using samples__in=qs, the yqs will be ordered by qs.
        yqs = models.Value.objects.filter(samples__in=qs).filter(name=y_val)

    print("XQS: ",xqs)
    print("YQS: ", yqs)
    x = [s.content_object.value for s in xqs]
    y = [s.content_object.value for s in yqs]

    x_type, x_search, x_cat = cat_map[x_val_category]
    y_type, y_search, y_cat = cat_map[y_val_category]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y,
                            mode=op_map[operation],
                            marker_color='rgba(152, 0, 0,0.9)'))
    layout = go.Layout(title=x_val + " vs "  + y_val,
                    xaxis={'title':x_val},
                    yaxis={'title':y_val})
    fig.layout = layout
    return to_html(fig, full_html=False), {'style': op_map[operation],
                                           'inv': [i.name for i in models.Investigation.objects.filter(pk__in=invs)],
                                           'x_cat': x_cat,
                                           'x_val': x_val,
                                           'y_cat': y_cat,
                                           'y_val': y_val}

def value_table_html(x_selected, y_selected=None):

    #choice field values are passed around as ints, so use this map to 'decode' them
    """
    selection_map = {'1': (Investigation, 'investigations__in', 'investigations__name'),
                     '2': (Sample, 'samples__in', 'samples__name'),
                     '3': (Feature, 'features__in', 'features__name'),
                     '4': (Step, 'steps__in', 'steps__name'),
                     '5': (Process, 'processes__in', 'processes__name'),
                     '6': (Analysis, 'analyses__in', 'anaylses__name'),
                     '7': (Result, 'results__in', 'results__name'),}
    """
    selection_map = {'1': (Investigation, 'investigations__isnull'),
                     '2': (Sample, 'samples__isnull', 'samples__name'),
                     '3': (Feature, 'features__isnull'),
                     '4': (Step, 'steps__isnull'),
                     '5': (Process, 'processes__isnull'),
                     '6': (Analysis, 'analyses__isnull'),
                     '7': (Result, 'results__isnull')}
    print(x_selected)
    """
    dep_q = {}
#    ind_q = {}
    indexes = set()
    for key in x_selected:
        mapped = selection_map[key]
        dep_q[mapped[1]] = mapped[0].objects.all()
        dep_q['name__in'] = x_selected[key]
        indexes.add(mapped[2])

    for key in y_selected:
        mapped = selection_map[key]
        ind_q[mapped[1]] = mapped[0].objects.all()
        if 'name__in' in ind_q:
            ind_q['name__in'] += y_selected[key]
        else:
            ind_q['name__in'] = y_selected[key]
        indexes.add(mapped[2])
"""
    keys = list(x_selected.keys())
    dep_tuple = selection_map[keys[0]]
    val_names = x_selected[keys[0]]

    klass = dep_tuple[0]

    #vqs = Value.objects.filter(**dep_q)
    qs = klass.objects.filter(values__signature__name__in=val_names).annotate(value_namee=F('values__signature__name'))
    df = qs.to_dataframe()
#    df = Value.queryset_to_table(vqs, indexes=indexes
    return df.to_html(classes=['table'])
