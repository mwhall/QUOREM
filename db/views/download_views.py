# ----------------------------------------------------------------------------
# path: quorem/db/forms/download_views.py
# authors: Mike Hall
# modified: 2022-06-20
# description: This file contains all views that are for downloading various
#              types of data.
# ----------------------------------------------------------------------------

from django.http import FileResponse, HttpResponse
from django.db.models import F, Q

###Stuff for searching
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector
)
###django pandas
from io import BytesIO

import pandas as pd

from ..plot import *
from ..models import *
from ..models.object import Object

def xls_download_view(request):
    model_map =  {'investigation': Investigation,
                  'sample': Sample,
                  'feature': Feature,
                  'analysis': Analysis,
                  'process': Process,
                  'step': Step,
                  'result': Result,}

    q = request.GET.get('q', '').strip() #user input from search bar
    if not q:
        q = request.GET.get('q2', '').strip()

    ##From search form
    selected_type = request.GET.get('otype', '')
    meta = request.GET.get('meta', '')

    #initialize vars for query
    query = None
    if q:
        query = SearchQuery(q)

    klass = model_map[selected_type]
    plural = klass.plural_name

    if meta:
        qs = klass.objects.filter(values__signature__name__in=[meta]).annotate(value_name=F('values__signature__name'))
    else:
        qs = klass.objects.all().annotate(value_name=F('values__signature__name'))

    df = klass.dataframe(**{plural: qs})

    with BytesIO() as b:
        writer = pd.ExcelWriter(b, engine="xlsxwriter")
        df.to_excel(writer)
        writer.save()
        response = HttpResponse(b.getvalue(), content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="hello.xls"'
        return response


def tax_table_download_view(request):
    taxonomy_result = request.GET.get('taxonomy_result','')
    count_matrix = request.GET.get('count_matrix','')
    taxonomic_level = request.GET.get('taxonomic_level','genus')
    normalize_method = request.GET.get('normalize_method',"None")
    metadata_collapse = request.GET.get('metadata_collapse',None)
    collapsed_df = collapsed_table(taxonomy_result, count_matrix, 
                                   taxonomic_level, normalize_method, 
                                   metadata_collapse)
    filename_suffix = "_taxpk_%s_matrixpk_%s" % (str(taxonomy_result), str(count_matrix))
    filename_suffix += "_%s" % (str(taxonomic_level),)
    filename_suffix += "_%s" % (normalize_method,)
    if metadata_collapse is not None and metadata_collapse != '':
        filename_suffix += "_%s" % (metadata_collapse,)
    with BytesIO() as b:
        writer = pd.ExcelWriter(b, engine="xlsxwriter")
        collapsed_df.to_excel(writer)
        writer.save()
        response = HttpResponse(b.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="taxonomy_table%s.xlsx"' % (filename_suffix,)
        return response

def csv_download_view(request):

    model_map =  {'investigation': Investigation,
                  'sample': Sample,
                  'feature': Feature,
                  'analysis': Analysis,
                  'process': Process,
                  'step': Step,
                  'result': Result,}

    q = request.GET.get('q', '').strip() #user input from search bar
    if not q:
        q = request.GET.get('q2', '').strip()

    ##From search form
    selected_type = request.GET.get('otype', '')
    meta = request.GET.get('meta', '')

    #initialize vars for query
    query = None
    if q:
        query = SearchQuery(q)

    klass = model_map[selected_type]
    plural = klass.plural_name
    if meta:
        qs = klass.objects.filter(values__signature__name__in=[meta]).annotate(value_name=F('values__signature__name'))
    else:
        qs = klass.objects.all().annotate(value_name=F('values__signature__name'))

    df = klass.dataframe(**{plural: qs})
    csv = df.to_csv()
    response = HttpResponse(csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hello.csv"'
    return response

def spreadsheet_download_view(request):
    id = request.GET.get('id', '')
    obj = request.GET.get('object','')
    wide = request.GET.get('wide','')
    format = request.GET.get('format', 'csv')
    result_id = request.GET.get('result_id', '')
    if result_id:
        result = Result.objects.get(pk=result_id)
        assert result.has_value("uploaded_spreadsheet", "file")
        artifact = result.get_value("uploaded_spreadsheet", "file").upload_file.file
        filename = artifact.name.split("/")[-1]
        response = HttpResponse(artifact.file, content_type='csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % (filename,)
        return response
    if str(wide).lower() in ["1", "true"]:
        wide = True
    else:
        wide = False
    Obj = Object.get_object_types(type_name=obj)
    df = Obj.objects.get(pk=id).dataframe(wide=wide)
    if format.lower() == "csv":
        df = df.to_csv()
        response = HttpResponse(df, content_type='text/csv')
    elif format.lower() in ["xls", "xlsx"]:
        with BytesIO() as b:
            writer = pd.ExcelWriter(b, engine="xlsxwriter")
            df.to_excel(writer)
            writer.save()
            response = HttpResponse(b.getvalue(), content_type='application/vnd.ms-excel')
    else:
        raise ValueError("Unrecognized spreadsheet format '%s'" % (format,))
    return response

def artifact_download_view(request):
    result_id = request.GET.get('result_id', '')
    if result_id:
        result = Result.objects.get(pk=result_id)
        assert result.has_value("uploaded_artifact", "file")
        artifact = result.get_value("uploaded_artifact", "file").upload_file.file
        filename = artifact.name.split("/")[-1]
        response = HttpResponse(artifact.file, content_type='zip/qza')
        response['Content-Disposition'] = 'attachment; filename="%s"' % (filename,)
        return response

