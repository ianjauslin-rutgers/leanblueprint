"""
Package Lean blueprint

This depends on the depgraph plugin. This plugin has to be installed but then it is
used automatically.

Options:
* project: lean project path

* showmore: enable buttons showing or hiding proofs (this requires the showmore plugin).

You can also add options that will be passed to the dependency graph package.
"""
import string
from pathlib import Path

from jinja2 import Template

from plasTeX import Command
from plasTeX.PackageResource import PackageTemplateDir, PackageCss
from plasTeX.Logging import getLogger

from plastexdepgraph.Packages.depgraph import item_kind

log = getLogger()

PKG_DIR = Path(__file__).parent
STATIC_DIR = Path(__file__).parent.parent/'static'

class home(Command):
    r"""\home{url}"""
    args = 'url:url'

    def invoke(self, tex):
        Command.invoke(self, tex)
        self.ownerDocument.userdata['project_home'] = self.attributes['url']
        return []

class github(Command):
    r"""\github{url}"""
    args = 'url:url'

    def invoke(self, tex):
        Command.invoke(self, tex)
        self.ownerDocument.userdata['project_github'] = self.attributes['url'].textContent.rstrip('/')
        return []

class dochome(Command):
    r"""\dochome{url}"""
    args = 'url:url'

    def invoke(self, tex):
        Command.invoke(self, tex)
        self.ownerDocument.userdata['project_dochome'] = self.attributes['url'].textContent
        return []

class leanok(Command):
    r"""\leanok"""
    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata['leanok'] = True

class notready(Command):
    r"""\notready"""
    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata['notready'] = True


class mathlibok(Command):
    r"""\mathlibok"""
    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata['leanok'] = True
        self.parentNode.userdata['mathlibok'] = True

class lean(Command):
    r"""\lean{decl list} """
    args = 'decls:list:nox'

    def digest(self, tokens):
        Command.digest(self, tokens)
        decls = [dec.strip() for dec in self.attributes['decls']]
        self.parentNode.setUserData('leandecls', decls)

class discussion(Command):
    r"""\discussion{issue_number} """
    args = 'issue:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.setUserData('issue', self.attributes['issue'].lstrip('#').strip())


CHECKMARK_TPL = Template("""
    {% if obj.userdata.leanok and ('proved_by' not in obj.userdata or obj.userdata.proved_by.userdata.leanok ) %}
    ✓
    {% endif %}
""")

LEAN_DECLS_TPL = Template("""
    {% if obj.userdata.leandecls %}
    <button class="modal lean">L∃∀N</button>
    {% call modal('Lean declarations') %}
        <ul class="uses">
          {% for lean, url in obj.userdata.lean_urls %}
          <li><a href="{{ url }}" class="lean_decl">{{ lean }}</a></li>
          {% endfor %}
        </ul>
    {% endcall %}
    {% endif %}
""")

GITHUB_ISSUE_TPL = Template("""
    {% if obj.userdata.issue %}
    <a class="github_link" href="{{ obj.ownerDocument.userdata.project_github }}/issues/{{ obj.userdata.issue }}">Discussion</a>
    {% endif %}
""")

LEAN_LINKS_TPL = Template("""
  {% if thm.userdata['lean_urls'] -%}
    {%- if thm.userdata['lean_urls']|length > 1 -%}
  <div class="tooltip">
      <span class="lean_link">Lean</span>
      <ul class="tooltip_list">
        {% for name, url in thm.userdata['lean_urls'] %}
           <li><a href="{{ url }}" class="lean_decl">{{ name }}</a></li>
        {% endfor %}
      </ul>
  </div>
    {%- else -%}
    <a class="lean_link lean_decl" href="{{ thm.userdata['lean_urls'][0][1] }}">Lean</a>
    {%- endif -%}
    {%- endif -%}
""")

GITHUB_LINK_TPL = Template("""
  {% if thm.userdata['issue'] -%}
  <a class="issue_link" href="{{ document.userdata['project_github'] }}/issues/{{ thm.userdata['issue'] }}">Discussion</a>
  {%- endif -%}
""")

def ProcessOptions(options, document):
    """This is called when the package is loaded."""

    # We want to ensure the depgraph and showmore packages are loaded.
    # We first need to make sure the corresponding plugins are used.
    # This is a bit hacky but needed for backward compatibility with
    # project who used the blueprint package before the depgraph one was
    # split.
    plugins = document.config['general'].data['plugins'].value
    if 'plastexdepgraph' not in plugins:
        plugins.append('plastexdepgraph')
    # And now load the package.
    document.context.loadPythonPackage(document, 'depgraph', options)
    if 'showmore' in options:
        if 'plastexshowmore' not in plugins:
            plugins.append('plastexshowmore')
        # And now load the package.
        document.context.loadPythonPackage(document, 'showmore', {})

    templatedir = PackageTemplateDir(path=PKG_DIR/'renderer_templates')
    document.addPackageResource(templatedir)

    jobname = document.userdata['jobname']
    outdir = document.config['files']['directory']
    outdir = string.Template(outdir).substitute({'jobname': jobname})

    def make_lean_data() -> None:
        """Build url and formalization status for nodes in the dependency graphs."""

        project_dochome = document.userdata.get('project_dochome',
                                               'https://leanprover-community.github.io/mathlib4_docs')

        for graph in document.userdata['dep_graph']['graphs'].values():
            nodes = graph.nodes
            for node in nodes:
                leandecls = node.userdata.get('leandecls', [])
                lean_urls = []
                for leandecl in leandecls:
                    lean_urls.append(
                        (leandecl,
                        f'{project_dochome}/find/#doc/{leandecl}'))

                node.userdata['lean_urls'] = lean_urls

                used = node.userdata.get('uses', [])
                node.userdata['can_state'] = all(thm.userdata.get('leanok')
                                                 for thm in used) and not node.userdata.get('notready', False)
                proof = node.userdata.get('proved_by')
                if proof:
                    used.extend(proof.userdata.get('uses', []))
                    node.userdata['can_prove'] = all(thm.userdata.get('leanok')
                                                     for thm in used)
                    node.userdata['proved'] = proof.userdata.get('leanok', False)
                else:
                    node.userdata['can_prove'] = False
                    node.userdata['proved'] = False

            for node in nodes:
                node.userdata['fully_proved'] = all(n.userdata['proved'] or item_kind(n) == 'definition' for n in graph.ancestors(node).union({node}))

    document.addPostParseCallbacks(150, make_lean_data)

    document.addPackageResource([PackageCss(path=STATIC_DIR/'blueprint.css')])

    colors = document.userdata['dep_graph']['colors'] = {
            'mathlib': ('darkgreen', 'Dark green'),
            'stated': ('green', 'Green'),
            'can_state': ('#FFAA33', 'Orange (dashed)'),
            'not_ready': ('red', 'Red'),
            'proved': ('#9CEC8B', 'Green'),
            'can_prove': ('#FFFFFF:#FFAA33', 'Orange (gradient)'),
            'defined': ('#1CAC78', 'Dark green')
            'fully_proved': ('#1CAC78', 'Dark green')
            }

    def colorizer(node) -> str:
        data = node.userdata

        color = ''
        if data.get('mathlibok'):
            color = colors['mathlib'][0]
        elif data.get('leanok'):
            color = colors['stated'][0]
        elif data.get('can_state'):
            color = colors['can_state'][0]
        elif data.get('notready'):
            color = colors['not_ready'][0]
        return color

    def fillcolorizer(node) -> str:
        data = node.userdata
        stated = data.get('leanok')
        can_state = data.get('can_state')
        can_prove = data.get('can_prove')
        proved = data.get('proved')
        fully_proved = data.get('fully_proved')

        fillcolor = ''
        if proved:
            fillcolor = colors['proved'][0]
        elif can_prove and (can_state or stated):
            fillcolor = colors['can_prove'][0]
        if item_kind(node) == 'definition':
            if stated:
                fillcolor = colors['defined'][0]
            elif can_state:
                fillcolor = colors['can_prove'][0]
        elif fully_proved:
            fillcolor = colors['fully_proved'][0]
        return fillcolor

    # determine style from node
    def stylerizer(node) -> str:
        data = node.userdata
        stated = data.get('leanok')
        can_state = data.get('can_state')
        can_prove = data.get('can_prove')
        proved = data.get('proved')
        fully_proved = data.get('fully_proved')

        style = ''
        if proved:
            style='filled'
        elif can_prove:
            if stated:
                style = 'filled'
            elif can_state:
                style = 'filled,dashed'
        elif can_state:
                style = 'dashed'
        if item_kind(node) == 'definition':
            if stated:
                style = 'filled'
            elif can_state:
                style = 'filled,dashed'
        elif fully_proved:
            style = 'filled'
        return style

    document.userdata['dep_graph']['colorizer'] = colorizer
    document.userdata['dep_graph']['fillcolorizer'] = fillcolorizer
    document.userdata['dep_graph']['stylerizer'] = stylerizer

    document.userdata['dep_graph']['legend'].extend([
      (f"{document.userdata['dep_graph']['colors']['can_state'][1]} border", "the <em>statement</em> of this result is ready to be formalized; all prerequisites are done"),
      (f"{document.userdata['dep_graph']['colors']['not_ready'][1]} border", "the <em>statement</em> of this result is not ready to be formalized; the blueprint needs more work"),
      (f"{document.userdata['dep_graph']['colors']['can_state'][1]} background", "the <em>proof</em> of this result is ready to be formalized; all prerequisites are done"),
      (f"{document.userdata['dep_graph']['colors']['proved'][1]} border", "the <em>statement</em> of this result is formalized"),
      (f"{document.userdata['dep_graph']['colors']['proved'][1]} background", "the <em>proof</em> of this result is formalized"),
      (f"{document.userdata['dep_graph']['colors']['fully_proved'][1]} background", "the <em>proof</em> of this result and all its ancestors are formalized")])

    document.userdata.setdefault('thm_header_extras_tpl', []).extend([CHECKMARK_TPL])
    document.userdata.setdefault('thm_header_hidden_extras_tpl', []).extend([LEAN_DECLS_TPL,
                                                         GITHUB_ISSUE_TPL])
    document.userdata['dep_graph'].setdefault('extra_modal_links_tpl', []).extend([
        LEAN_LINKS_TPL, GITHUB_LINK_TPL])
