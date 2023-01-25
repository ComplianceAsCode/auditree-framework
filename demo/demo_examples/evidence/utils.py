from compliance.config import get_config


def get_gh_orgs():
    return get_config().get('org.gh.orgs')
