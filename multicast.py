import math


class TrustDomain:
    def __init__(self, name):
        self.name = name
        self.router = None

    def __str__(self):
        return self.name


class Node:
    def __init__(self, name, trust_domain):
        self.name = name
        self.trust_domain = trust_domain
        self.neighbors = set()
        self.routing = {}

        self.next_hop_to_rib = None
        self.distance_to_rib = math.inf

    def get_distance_to_rib(self):
        return self.distance_to_rib

    def add_neighbor(self, neighbor, link_cost=1):
        self.neighbors.add(neighbor)
        neighbor.neighbors.add(self)

        # Check if the new neighbor is a better path to the RIB
        if (
            neighbor.get_distance_to_rib() + link_cost < self.get_distance_to_rib()
            or self.next_hop_to_rib == None
        ):
            self.next_hop_to_rib = neighbor
            self.distance_to_rib = neighbor.get_distance_to_rib() + link_cost

        # Notify the RIB that the link has been added
        self.rib_add_link(self, neighbor, link_cost)

    def rib_add_link(self, node1, node2, link_cost):
        self.next_hop_to_rib.rib_add_link(node1, node2, link_cost)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Client(Node):
    def __init__(self, name, switch):
        super().__init__(name, switch.trust_domain)
        if switch != None:
            self.switch = switch
            self.next_hop_to_rib = switch
            switch.add_neighbor(self)

    def __str__(self):
        return self.name


class Router(Node):  # A Router is just a Switch with additional functionality
    def __init__(self, name, parent_router, trust_domain):
        super().__init__(name, trust_domain)

        if trust_domain:
            trust_domain.router = self

        self.parent_router = parent_router
        self.children = set()

        # Stuff below here is the RIB (lives inside the router)
        self.rib_multicast_groups = {}
        self.rib_nodes = set()
        self.rib_edges = set()
        # self.rib_nexthop_entries = {}

    def add_neighbor(self, neighbor, link_cost=1):
        self.neighbors.add(neighbor)
        neighbor.neighbors.add(self)

        # Check if the new neighbor is a better path to the parent RIB
        # However, it can only be a path to the parent RIB if it is not part of the same trust domain
        if neighbor.trust_domain != self.trust_domain and (
            neighbor.get_distance_to_rib() + link_cost < self.distance_to_rib
            or self.next_hop_to_rib == None
        ):
            self.next_hop_to_rib = neighbor
            self.distance_to_rib = neighbor.get_distance_to_rib() + link_cost

        # Notify the parent RIB that the link has been added
        self.next_hop_to_rib.rib_add_link(self, neighbor, link_cost)

    def get_distance_to_rib(self):
        return 0

    def rib_add_link(self, node1, node2, link_cost):
        self.rib_nodes.add(node1)
        self.rib_nodes.add(node2)
        self.rib_edges.add((node1, node2, link_cost))

    # def create_multicast_group(self, group_name, node):
    #     # Create new multicast group in RIB
    #     self.rib_multicast_groups[group_name] = set([node])

    #     # Create multicast group in parent RIB
    #     if self.parent_router != None:
    #         # We don't want to add a switch to the parent router's RIB, so we find the leaf router
    #         leaf_router = node if isinstance(node, Router) else node.trust_domain.router
    #         self.parent_router.create_multicast_group(group_name, leaf_router)

    # def add_multicast_group_member(self, group, node):
    #     if node not in self.rib_multicast_groups[group]:
    #         self.rib_multicast_groups[group].add(node)

    #         # Propagate to parent
    #         leaf_router = node if isinstance(node, Router) else node.trust_domain.router
    #         if self.parent_router != None:
    #             self.parent_router.add_multicast_group_member(group, leaf_router)


def main():
    routerRoot = Router("A", None, None)

    # Create trust domain A with one router and two switches, and two clients for each switch
    domainA = TrustDomain("domainA")
    routerA = Router("routerA", routerRoot, domainA)
    switch1 = Node("switch1", domainA)
    switch1.add_neighbor(routerA)
    switch2 = Node("switch2", domainA)
    switch2.add_neighbor(routerA)
    client1 = Client("client1", switch1)
    client2 = Client("client2", switch1)
    client3 = Client("client3", switch2)
    client4 = Client("client4", switch2)

    # Create trust domain B with one router and two switches, and two clients for each switch
    domainB = TrustDomain("B")
    routerB = Router("routerB", routerRoot, domainB)
    switch3 = Node("switch3", domainB)
    switch3.add_neighbor(routerB)
    switch4 = Node("switch4", domainB)
    switch4.add_neighbor(routerB)
    client5 = Client("client5", switch3)
    client6 = Client("client6", switch3)
    client7 = Client("client7", switch4)
    client8 = Client("client8", switch4)

    # Create multicast tree in domain A
    # routerA.create_multicast_group("group1", switch1)

    # print(routerRoot.rib_multicast_groups)
    # print(routerA.rib_multicast_groups)

    print(routerRoot.rib_nodes)
    print(routerRoot.rib_edges)


main()
