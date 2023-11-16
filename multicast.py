class TrustDomain:
    def __init__(self, name, router):
        self.name = name
        self.router = router

    def __str__(self):
        return self.name


class Client:
    def __init__(self, name, trust_domain):
        self.name = name
        self.trust_domain = trust_domain
        self.switch = None

    def __str__(self):
        return self.name


class Switch:
    def __init__(self, name, trust_domain):
        self.name = name
        self.trust_domain = trust_domain
        self.neighbors = set()
        self.routing = {}

    def __str__(self):
        return self.name


class Router(Switch):
    def __init__(self, name, parent_router, trust_domain):
        super().__init__(name, trust_domain)
        self.parent_router = parent_router
        self.children = set()

        # Stuff below here is the RIB (lives inside the router)
        self.rib_multicast_groups = {}
        # self.rib_nexthop_entries = {}

    def create_multicast_group(self, group_name, node):
        # Create new multicast group in RIB
        self.rib_multicast_groups[group_name] = set([node])

        # Create multicast group in parent RIB
        if self.parent_router != None:
            leaf_router = node if isinstance(node, Router) else node.trust_domain.router
            self.parent_router.create_multicast_group(group_name, leaf_router)

    def add_multicast_group_member(self, group, node):
        if node not in self.rib_multicast_groups[group]:
            self.rib_multicast_groups[group].add(node)

            # Propagate to parent
            leaf_router = node if isinstance(node, Router) else node.trust_domain.router
            if self.parent_router != None:
                self.parent_router.add_multicast_group_member(group, leaf_router)

    def get_nexthop(self, address):
        return self.rib_nexthop_entries[address]
