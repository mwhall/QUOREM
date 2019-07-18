import markdown
import re
from wiki.models.urlpath import URLPath
from wiki.models.article import Article, ArticleRevision
from wiki.core.exceptions import NoRootURL
from django.apps import apps
from django.contrib.staticfiles.storage import staticfiles_storage

def get_content_from_file(staticfile):
    #url = staticfiles_storage.url(staticfile)
    with open(staticfile, 'r') as sfile:
       return sfile.read()

def initialize_documentation(root):
    try:
        URLPath.get_by_path("use")
    except:
        URLPath.create_urlpath(root, slug="use", 
                                 title="Using QUOR'em",
                                 content=get_content_from_file("quorem/static/docs/use.md"))
    try:
        URLPath.get_by_path("develop")
    except:
        URLPath.create_urlpath(root, slug="develop",
            title="Developing QUOR'em",
            content=get_content_from_file("quorem/static/docs/develop.md"))
    try:
        URLPath.get_by_path("deploy")
    except:
        URLPath.create_urlpath(root, slug="deploy",
            title="Deploying QUOR'em",
            content=get_content_from_file("quorem/static/docs/deploy.md"))

#Wire up the reports here so that it can all be imported in one function
def get_wiki_report(report_name, **kwargs):
    new_content = "# Automated Report\r\n\r\n"
    if report_name=="investigation":
        new_content += investigation_markdown(**kwargs)
    elif report_name=="sample":
        new_content += sample_markdown(**kwargs)
#    elif report_name=="replicate":
#    elif report_name=="protocol":
#    elif report_name=="pipeline":
    else:
        raise ValueError("Unknown report name %s" % (report_name,))
    return new_content + "\r\n"

def investigation_markdown(pk=None):
    Investigation = apps.get_model('db.Investigation')
    Sample = apps.get_model('db.Sample')
    new_content = ""
    if pk is None: #Return the investigation list
        new_content += "Investigation Name | Institution | Description\r\n"
        new_content += "-------------------|-------------|------------\r\n"
        for investigation in Investigation.objects.all():
            new_content += "[%s](wiki:%d)|%s|%s\r\n" % (investigation.name,
                                             investigation.pk,
                                             investigation.institution,
                                             investigation.description)
    else:
        investigation = Investigation.objects.get(pk=pk)
        new_content += "**Name**: %s\r\n\r\n" % (investigation.name,)
        new_content += "**Institution**: %s\r\n\r\n" % (investigation.institution,)
        new_content += "**Description**: %s\r\n\r\n" % (investigation.description,)
        samples = Sample.objects.filter(investigation=investigation)
        sample_links = ", ".join(["[%s](/wiki/sample/%d)" % (re.escape(x.name), x.pk) for x in samples])
        new_content += "**Samples**: %s\r\n\r\n" % (sample_links,)

    return new_content
        
def sample_markdown(pk=None):
    new_content = ""
    Sample = apps.get_model('db.Sample')
    if pk is None:
        raise NotImplementedError("No Sample List Markdown Report")
    else:
        sample = Sample.objects.get(pk=pk)
        new_content += "**Name**: %s\r\n\r\n" % (sample.name,)
        new_content += "**Investigation**: %s\r\n\r\n" % (sample.investigation.name,)
    return new_content

def refresh_automated_report(slug, pk=None):
    Investigation = apps.get_model('db.Investigation')
    Sample = apps.get_model('db.Sample')
    BiologicalReplicate = apps.get_model('db.BiologicalReplicate')
    BiologicalReplicateProtocol = apps.get_model('db.BiologicalReplicateProtocol')
    ComputationalPipeline = apps.get_model('db.ComputationalPipeline')
    
    slug_to_model = {'investigation': Investigation,
                     'sample': Sample}
    

    if pk is None:
        article = URLPath.get_by_path(slug).article
    else:
        try:
            article = URLPath.get_by_path("%s/%d" % (slug,pk)).article
        except URLPath.DoesNotExist:
            try:
                obj = slug_to_model[slug].objects.get(pk=pk)
            except slug_to_model[slug].DoesNotExist:
                raise ValueError("No such pk found, no wiki entry to update")
            try:
                root = URLPath.get_by_path(slug)
            except URLPath.DoesNotExist:
                raise ValueError("No such slug found, is your wiki initialized?")
            print("Creating new article")
            try:
                slug_to_model[slug]._meta.get_field("name")
                title = obj.name
            except:
                title = "%s %d" % (slug, pk)
            article = URLPath.create_urlpath(root, 
                                   slug="%d" % (pk,),
                                   title=title,
                                   content="This page has been automatically" \
                                           "generated. You may edit at will").article
    current_content = article.current_revision.content
    md=markdown.Markdown()
    inv_html = md.convert(current_content)
    new_content = ""
    skip_until_h1 = False
    added = False
    for line in md.lines:
        if skip_until_h1 & (not line.startswith("# ")):
            continue
        elif skip_until_h1 & line.startswith("# "):
            skip_until_h1 = False
        if line == '# Automated Report':
            new_content += get_wiki_report(slug, pk=pk)
            skip_until_h1 = True
            added = True
        else:
            new_content += line + "\r\n"
    if not added:
        new_content += get_wiki_report(slug, pk=pk)
    article_revision = ArticleRevision(title=article.current_revision.title,
                                       content=new_content)
    article.add_revision(article_revision)

def initialize_wiki():
    try:
        root = URLPath.root()
    except NoRootURL:
        print("Root URL not found, creating...")
        root = URLPath.create_root(title="QUOR'EM Wiki",
                                   content=get_content_from_file("quorem/static/docs/root.md"))
    article_revision = ArticleRevision(title=root.article.current_revision.title,
                                                   content=get_content_from_file("quorem/static/docs/root.md"))
    root.article.add_revision(article_revision)
    try:
        investigation = URLPath.get_by_path("investigation")
    except URLPath.DoesNotExist:
        print("Investigation page not found, creating...")
        URLPath.create_urlpath(root, slug="investigation", 
                                     title="List of Investigations",
                                     content="""This page lists the 
        investigations that are present in your QUOR'EM database. You may
        edit anything on this page, except the Automated Report 
        section.\r\n\r\n""")

    try:
        protocol = URLPath.get_by_path("protocol")
    except URLPath.DoesNotExist:
        print("Protocol page not found, creating...")
        URLPath.create_urlpath(root, slug="protocol", 
                                     title="List of Protocols",
                                     content="""This page lists the 
        protocols that are present in your QUOR'EM database. You may
        edit anything on this page, except the Automated Report 
        section.\r\n\r\n""")

    try:
        pipeline = URLPath.get_by_path("pipeline")
    except URLPath.DoesNotExist:
        print("Pipeline page not found, creating...")
        URLPath.create_urlpath(root, slug="pipeline", 
                                     title="List of Pipelines",
                                     content="""This page lists the 
        pipelines that are present in your QUOR'EM database. You may
        edit anything on this page, except the Automated Report 
        section.\r\n\r\n""")
    try:
        sample = URLPath.get_by_path("sample")
    except URLPath.DoesNotExist:
        print("Sample page not found, creating...")
        URLPath.create_urlpath(root, slug="sample",
                                     title="List of Samples",
                                     content="This page lists the samples that are present in your QUOR'EM database. You may edit anything on this page, except the Automated Report section.\r\n\r\n")

    initialize_documentation(root)


        
