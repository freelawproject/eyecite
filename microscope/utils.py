from lxml import html


def get_visible_text(html_content):
    """Given HTML markup, only text that is visible
    Adopted from https://github.com/freelawproject/juriscraper/blob/master/juriscraper/lib/html_utils.py#L163

    :param html_content: The HTML string
    :return: Text that is visible
    """
    html_tree = html.fromstring(html_content)
    text = html_tree.xpath(
        """//text()[normalize-space() and not(
            parent::style |
            parent::link |
            parent::head |
            parent::script)]"""
    )
    return " ".join(text)
