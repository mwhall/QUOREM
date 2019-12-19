import markdown
from django.contrib.staticfiles import finders
from wiki.models.urlpath import URLPath
from wiki.models.article import Article, ArticleRevision
from wiki.core.exceptions import NoRootURL

base_manifest = ["root.md"]

docs_manifest = ["root.md", "develop.md", "use.md", "deploy.md",
                 "use/input.md", "use/search.md", "use/wiki.md", 
                 "develop/install.md", "develop/jupyter.md",
                 "develop/qiime2.md", "develop/reports.md", "develop/schema.md",
                 "deploy/backup.md", "deploy/install.md", "deploy/secure.md",
                 "deploy/serve.md", "deploy/storage.md", "deploy/upgrade.md"]

class WikiStatic(object):
    def __init__(self, slug, template, prefix="/"):
        print("Wiki init slug %s template %s prefix %s" % (slug, template, prefix))
        #Slug is a string, in the case of a static wiki page
        self.slug = slug
        self.prefix = prefix
        self.template = template
        self.content, self.title = self.process_template()
        self.root = self.get_root()

    def get_root(self):
        try:
            base_root = URLPath.get_by_path(path="")
        except NoRootURL:
            if (self.slug == "root") and (self.prefix=="/"):
                root = URLPath.create_root(title="QUOREM Wiki",
                                           content=self.content)
                return root
            else:
                raise ValueError("No root created for prefix '%s'. Make sure root.md is processed first" % (self.prefix,))
        try:
            root = URLPath.get_by_path(self.prefix)
        except URLPath.DoesNotExist:
            if (self.slug == "root") and (self.prefix != "/"):
                root = URLPath.create_urlpath(base_root, slug=self.prefix,
                                       title=self.title,
                                       content=self.content)
            else:
                raise ValueError("No root created for prefix '%s'." % (self.prefix,))
        return root


    def update_wiki(self):
        if (self.slug == "root"):
            return #Already made in get_root() if not made
        try:
            wiki_page = URLPath.get_by_path(self.prefix+"/"+self.slug)
            #Create a new revision and update with the template content
            article = wiki_page.article
            article_revision = ArticleRevision(title=article.current_revision.title,
                                               content=self.content)
            article.add_revision(article_revision)
        except URLPath.DoesNotExist:
            print("Creating wiki page for slug %s prefix %s" % (self.slug, self.prefix))
            wiki_page = URLPath.create_urlpath(self.root, slug=self.slug,
                                             title=self.title,
                                             content=self.content)
            
    def process_template(self):
        #Load self.template and read it
        filepath = finders.find("markdown/" + self.prefix + "/" + self.template)
        if filepath is not None:
            with open(filepath, 'r') as md_file:
                md_str = md_file.read()
                md = markdown.Markdown(extensions=['meta'])
                html = md.convert(md_str)
                if 'title' in md.Meta:
                    title = md.Meta['title'][0]
                else:
                    title = self.slug.capitalize()
                content = md_str
        else:
            raise FileNotFoundError("Static document %s not found" % (self.template,))
        return content, title
