class TrustDomain:
    def __init__(self, name):
        self.name = name
        self.router = None

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

    def __repr__(self):
        return self.name


class Router(Switch):  # A Router is a subclass of a Switch
    def __init__(self, name, parent_router, trust_domain):
        super().__init__(name, trust_domain)

        if trust_domain:
            trust_domain.router = self

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
            # We don't want to add a switch to the parent router's RIB, so we find the leaf router
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


def main():
    routerRoot = Router("A", None, None)

    # Create trust domain A with one router and two switches
    domainA = TrustDomain("domainA")
    routerA = Router("routerA", routerRoot, domainA)
    switch1 = Switch("switch1", domainA)
    switch1.neighbors.add(routerA)
    switch2 = Switch("switch2", domainA)
    switch2.neighbors.add(routerA)

    # Create trust domain B with one router and two switches
    domainB = TrustDomain("B")
    routerB = Router("routerB", routerRoot, domainB)
    switch3 = Switch("switch3", domainB)
    switch3.neighbors.add(routerB)
    switch4 = Switch("switch4", domainB)
    switch4.neighbors.add(routerB)

    # Create multicast tree in domain A
    routerA.create_multicast_group("group1", switch1)

    print(routerRoot.rib_multicast_groups)
    print(routerA.rib_multicast_groups)


main()
