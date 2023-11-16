class TrustDomain:
    def __init__(self, name, router):
        self.name = name
        self.router = router

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash((self.name))


class Client:
    def __init__(self, name, trust_domain):
        self.name = name
        self.trust_domain = trust_domain
        self.switch = None

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash((self.name, self.trust_domain))


class Switch:
    def __init__(self, name, trust_domain):
        self.name = name
        self.trust_domain = trust_domain
        self.neighbors = set()
        self.routing = {}

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash((self.name, self.trust_domain))


class Router(Switch):
    def __init__(self, name, parent_router, trust_domain):
        super().__init__(name, trust_domain)
        self.parent_router = parent_router

        # Stuff below here is the RIB (lives inside the router)
        self.rib_multicast_groups = {}
        # self.rib_nexthop_entries = {}

    def create_multicast_group(self, group_name, creator):
        # Create new multicast group in RIB
        self.rib_multicast_groups[group_name] = set([creator])

        # Add multicast group to parent RIB
        if self.parent_router != None:
            leaf_router = creator.trust_domain.router
            self.parent_router.create_multicast_group(group_name, leaf_router)

    def add_multicast_group_member(self, group, member):
        self.rib_multicast_groups[group].add(member)

    def get_nexthop(self, address):
        return self.rib_nexthop_entries[address]
