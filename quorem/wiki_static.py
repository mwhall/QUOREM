import markdown
from django.contrib.staticfiles import finders
from wiki.models.urlpath import URLPath
from wiki.models.article import Article, ArticleRevision
from wiki.core.exceptions import NoRootURL

docs_manifest = ["root.md", "develop.md", "use.md", "deploy.md",
                 "use/input.md", "use/search.md", "use/wiki.md", 
                 "develop/install.md", "develop/jupyter.md",
                 "develop/qiime2.md", "develop/reports.md", "develop/schema.md",
                 "deploy/backup.md", "deploy/install.md", "deploy/secure.md",
                 "deploy/serve.md", "deploy/storage.md", "deploy/upgrade.md"]

class WikiStatic(object):
    def __init__(self, slug, template):
        #Slug is a string, in the case of a static wiki page
        self.slug = slug
        self.template = template
        self.content, self.title = self.process_template()
        self._refresh_root()

    def _refresh_root(self):
        if "/" not in self.slug:
            try:
                self.root = URLPath.get_by_path("/")
            except:
                if self.slug == "root":
                    self.root = self._create_root()
                else:
                    raise ValueError("No root created. Make sure root.md is processed first")
        else:
            try:
                root_name = "/".join(self.slug.split("/")[:-1])
                self.root = URLPath.get_by_path(root_name)
            except:
                self.root = None


    def update_wiki(self):
        try:
            print("Retrieving slug %s" % (self.slug,))
            if self.slug == "root":
                self.slug = "/"
            wiki_page = URLPath.get_by_path(self.slug)
            #Create a new revision and update with the template content
            article = wiki_page.article
            article_revision = ArticleRevision(title=article.current_revision.title,
                                               content=self.content)
            article.add_revision(article_revision)
        except URLPath.DoesNotExist:
            print("Creating a new article")
            if self.root is None:
                self._refresh_root()
            print("Using root %s" % (self.root,))
            print("Pushing to slug %s"% (self.slug,))
            base_slug = self.slug.split("/")[-1]
            wiki_page = URLPath.create_urlpath(self.root, slug=base_slug,
                                         title=self.title,
                                         content=self.content)
            
    def process_template(self, static_prefix="docs/"):
        #Load self.template and read it
        filepath = finders.find(static_prefix + self.template)
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

    def _create_root(self):
        root = URLPath.create_root(title="QUOREM Wiki",
                                   content=self.content)
        return root
