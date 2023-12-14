from enum import Enum
import time
import random

# Enable to print every message received at any node. Disable to only print messages received at clients.
DEBUG = False
USE_ENCRYPTION = False


class MessageTypes(Enum):
    PING = 0
    RIB_ADD_LINK = 1
    RIB_ADD_OWNERSHIP = 2
    RIB_QUERY_NEXT_HOP = 3
    ADD_MULTICAST_GROUP = 4
    CLIENT_CREATE_MULTICAST_GROUP = 5
    CLIENT_JOIN_MULTICAST_GROUP = 6
    ROUTER_JOIN_MULTICAST_GROUP = 7
    RIB_QUERY_NEXT_MULTICAST_HOPS = 8
    MULTICAST_GROUP_TRANSFER_LCA = 9
    MULTICAST_GROUP_REQUEST_CREDENTIALS = 10
    MULTICAST_GROUP_SEND_CREDENTIALS = 11


class NodeTypes(Enum):
    ROUTER = 0
    SWITCH = 1
    CLIENT = 2


TOTAL_EDGE_WEIGHT = 0
TREE_BUILD_WEIGHT = 0
ROUTER_ROOT_MESSAGES = 0


class Message:
    def __init__(self, content, type: MessageTypes):
        self.content = content
        self.type: MessageTypes = type

    def __str__(self):
        return f"Message({self.type}, {self.content})"

    def __repr__(self):
        return f"Message({self.type}, {self.content})"


class Node:
    def __init__(self, name, parent_router):
        self.name = name
        self.parent_router = parent_router
        self.neighbors = set()
        self.routing_table = {self: (None, 0)}
        self.multicast_routing_table = {}
        self.type = -1

    def get_trust_domain_router(self):
        return self if isinstance(self, Router) else self.parent_router

    def get_next_hop(self, destination):
        if destination not in self.routing_table:
            # print(f"[{self}] {destination} not in routing table. Querying RIB...")

            # Query RIB for next hop
            message = Message(
                content=(self, destination), type=MessageTypes["RIB_QUERY_NEXT_HOP"]
            )

            (next_hop, distance) = self.send_message(self, self.parent_router, message)

            self.routing_table[destination] = (next_hop, distance)

        return self.routing_table[destination]

    def get_next_multicast_hops(self, multicast_group):
        if multicast_group not in self.multicast_routing_table:
            # print(
            #     f"[{self}] {multicast_group} not in multicast routing table. Querying RIB..."
            # )

            # Query RIB for next hop
            message = Message(
                content=multicast_group,
                type=MessageTypes["RIB_QUERY_NEXT_MULTICAST_HOPS"],
            )

            next_hops = self.send_message(self, self.parent_router, message)

            self.multicast_routing_table[multicast_group] = next_hops

        return self.multicast_routing_table[multicast_group]

    def add_neighbor(self, neighbor, link_cost=1, reverse=False):
        self.neighbors.add(neighbor)

        # Add the neighbor itself to routing table unless there is already a shorter path to it
        if (
            neighbor not in self.routing_table
            or link_cost < self.routing_table[neighbor][1]
        ):
            self.routing_table[neighbor] = (neighbor, link_cost)

        # Check if the new neighbor has better paths to other nodes
        for destination, (_, distance_from_neighbor) in neighbor.routing_table.items():
            if (
                destination not in self.routing_table
                or distance_from_neighbor + link_cost
                < self.routing_table[destination][1]
            ):
                self.routing_table[destination] = (
                    neighbor,
                    distance_from_neighbor + link_cost,
                )

        # Do if check to avoid back-and-forth recursion
        if not reverse:
            # Register neighborship on the other side
            neighbor.add_neighbor(self, link_cost, reverse=True)

            # Notify RIB of the new link
            if isinstance(self, Router):
                self.rib_add_link(self, neighbor, link_cost)
            else:
                message = Message(
                    content=(self, neighbor, link_cost), type=MessageTypes.RIB_ADD_LINK
                )
                self.send_message(self, self.parent_router, message)

    def send_message(self, source, destination, message):
        next_hop = self.get_next_hop(destination=destination)[0]
        global TOTAL_EDGE_WEIGHT
        global ROUTER_ROOT_MESSAGES

        if str(self) == "RouterRoot":
            ROUTER_ROOT_MESSAGES += 1

        if self.type == NodeTypes.ROUTER and next_hop.type == NodeTypes.ROUTER:
            TOTAL_EDGE_WEIGHT += 100
            # print(f"CROSS {self.name} {next_hop.name}")
        else:
            TOTAL_EDGE_WEIGHT += 1
            # print(self.name, next_hop.name)

        return next_hop.receive_message(source, destination, message)

    def receive_message(self, source, destination, message):
        if self == destination:
            # Handle message
            return self.handle_message(source, message)
        else:
            # Forward to next hop
            return self.send_message(source, destination, message)

    def send_multicast_message(self, source, multicast_group, message, visited=set()):
        next_hops = self.get_next_multicast_hops(multicast_group)
        updated_visited = visited.copy()
        updated_visited.add(self)

        destinations = [next_hop for next_hop in next_hops if next_hop not in visited]
        pass

        global ROUTER_ROOT_MESSAGES
        if str(self) == "RouterRoot":
            ROUTER_ROOT_MESSAGES += len(destinations)

        global TOTAL_EDGE_WEIGHT
        for nh in destinations:
            if self.type == NodeTypes.ROUTER and nh.type == NodeTypes.ROUTER:
                TOTAL_EDGE_WEIGHT += 100
                # print(f"CROSS {self.name} {nh.name}")
            else:
                TOTAL_EDGE_WEIGHT += 1
                # print(self.name, nh.name)

        return [
            destination.receive_multicast_message(
                source, multicast_group, message, updated_visited
            )
            for destination in destinations
        ]

    def receive_multicast_message(self, source, multicast_group, message, visited):
        if (
            hasattr(self, "multicast_groups")
            and multicast_group in self.multicast_groups
        ):
            # Handle message
            return self.handle_message(source, message)
        else:
            # Forward to next hops
            return self.send_multicast_message(
                source, multicast_group, message, visited
            )

    def handle_message(self, source, message):
        if message.type == MessageTypes.MULTICAST_GROUP_REQUEST_CREDENTIALS:
            # Respond with credentials
            message = Message(
                content=(),
                type=MessageTypes.MULTICAST_GROUP_SEND_CREDENTIALS,
            )
            self.send_message(self, source, message)
        elif message.type == MessageTypes.MULTICAST_GROUP_SEND_CREDENTIALS:
            # print(f"[{self}] Received credentials from {source}.")
            pass
        else:
            # print(f"[{self}] Received message from {source}: {message}")
            pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Switch(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)
        self.type = NodeTypes.SWITCH


class Client(Node):
    def __init__(self, name, node_connected_to):
        parent_router = (
            node_connected_to
            if isinstance(node_connected_to, Router)
            else node_connected_to.parent_router
        )
        super().__init__(name, parent_router)
        self.multicast_groups = set()

        # Register the connected node as a neighbor
        self.add_neighbor(node_connected_to)
        self.type = NodeTypes.CLIENT

    def handle_message(self, source, message):
        super().handle_message(source, message)

    def create_multicast_group(self, group_name):
        message = Message(
            content=(group_name, self.get_trust_domain_router(), self),
            type=MessageTypes.CLIENT_CREATE_MULTICAST_GROUP,
        )
        self.send_message(self, self.parent_router, message)
        self.multicast_groups.add(group_name)

    def join_multicast_group(self, group_name):
        # Send message to the trust domain router
        message = Message(
            content=group_name, type=MessageTypes.CLIENT_JOIN_MULTICAST_GROUP
        )
        owner = self.send_message(self, self.parent_router, message)

        if USE_ENCRYPTION:
            # Send message to the multicast group owner to get credentials
            message = Message(
                content=group_name,
                type=MessageTypes.MULTICAST_GROUP_REQUEST_CREDENTIALS,
            )
            self.send_message(self, owner, message)

        self.multicast_groups.add(group_name)


class Router(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)

        # Everything below here is the RIB (lives inside the router)
        self.rib_nodes = set()
        self.rib_edges = set()
        self.rib_child_router_ownerships = {}
        self.rib_multicast_groups = {}

        self.type = NodeTypes.ROUTER

    def get_next_hop(self, destination):
        if destination not in self.routing_table:
            # print(
            #     f"[{self}] {destination} not in routing table of {self}. Querying RIB..."
            # )

            # Query RIB for next hop
            (next_hop, distance) = self.rib_query_next_hop(self, destination)

            self.routing_table[destination] = (next_hop, distance)

        return self.routing_table[destination]

    def get_next_multicast_hops(self, multicast_group):
        if multicast_group not in self.multicast_routing_table:
            # print(
            #     f"[{self}] {multicast_group} not in multicast routing table. Querying RIB..."
            # )

            # Query RIB for next hop
            next_hops = self.rib_query_next_multicast_hops(self, multicast_group)

            self.multicast_routing_table[multicast_group] = next_hops

        return self.multicast_routing_table[multicast_group]

    def handle_message(self, source, message):
        if DEBUG:
            super().handle_message(source, message)

        if message.type == MessageTypes.RIB_QUERY_NEXT_HOP:
            (start, destination) = message.content
            next_hop, distance = self.rib_query_next_hop(start, destination)
            return (next_hop, distance)

        elif message.type == MessageTypes.RIB_QUERY_NEXT_MULTICAST_HOPS:
            multicast_group = message.content
            next_hops = self.rib_query_next_multicast_hops(source, multicast_group)
            return next_hops

        elif message.type == MessageTypes.RIB_ADD_LINK:
            (node1, node2, link_cost) = message.content
            self.rib_add_link(node1, node2, link_cost)

        elif message.type == MessageTypes.RIB_ADD_OWNERSHIP:
            (router, node) = message.content
            self.rib_add_ownership(router, node)

        elif message.type == MessageTypes.ADD_MULTICAST_GROUP:
            group_name, lowest_common_ancestor, owner = message.content
            self.rib_add_multicast_group(
                source, group_name, lowest_common_ancestor, owner
            )

        elif message.type == MessageTypes.CLIENT_CREATE_MULTICAST_GROUP:
            group_name, lowest_common_ancestor, owner = message.content
            self.rib_add_multicast_group(
                source, group_name, lowest_common_ancestor, owner=source
            )
            self.rib_router_join_multicast_group(
                source.get_trust_domain_router(), group_name
            )
            self.rib_client_join_multicast_group(source, group_name)

        elif message.type == MessageTypes.CLIENT_JOIN_MULTICAST_GROUP:
            group_name = message.content
            owner = self.rib_client_join_multicast_group(source, group_name)
            return owner

        elif message.type == MessageTypes.ROUTER_JOIN_MULTICAST_GROUP:
            group_name = message.content
            owner = self.rib_router_join_multicast_group(source, group_name)
            return owner

        elif message.type == MessageTypes.MULTICAST_GROUP_TRANSFER_LCA:
            group_name = message.content
            return self.rib_multicast_group_transfer_lca(source, group_name)

    def rib_query_next_hop(self, start, destination):
        # If the destination is in the same trust domain, use Dijkstra's algorithm within the domain
        if destination.parent_router == self:
            next_hop, distance = self.dijkstra_path_to_single_node(start, destination)
            return next_hop, distance

        # If the destination is not in the same trust domain, first route to the sender's trust domain router
        # Then, route to the destination's trust domain router
        else:
            if not isinstance(start, Router):
                # Route to the sender's trust domain router
                next_hop, distance = self.dijkstra_path_to_single_node(
                    start, start.parent_router
                )
                return next_hop, distance

            # Try to route to destination's trust domain router with local RIB
            result = self.dijkstra_path_to_single_node(
                start, destination.get_trust_domain_router()
            )
            if result:
                return result

            # Else ask the parent RIB for the next hop
            if self.parent_router:
                message = Message(
                    content=(start, destination),
                    type=MessageTypes["RIB_QUERY_NEXT_HOP"],
                )

                return self.send_message(self, self.parent_router, message)

        return None  # Path not found

    # Dijkstra's algorithm for finding next hop (thanks, ChatGPT)
    def dijkstra_path_to_single_node(self, start, destination):
        # Initialize distance and previous node dictionaries
        distances = {node: float("infinity") for node in self.rib_nodes}
        previous_nodes = {node: None for node in self.rib_nodes}

        # Initialize the priority list
        queue = [(0, start)]
        distances[start] = 0

        while queue:
            # Find and remove the node with the smallest distance
            current_distance, current_node = min(queue, key=lambda x: x[0])
            queue.remove((current_distance, current_node))

            # If destination is reached, backtrack to find the first hop
            if current_node == destination:
                first_hop = backtrack_first_hop(start, destination, previous_nodes)
                return first_hop, distances[destination]

            # Iterate over neighbors of the current node
            for edge in self.rib_edges:
                if current_node in edge:
                    neighbor = edge[0] if current_node == edge[1] else edge[1]
                    length = edge[2]
                    new_distance = current_distance + length

                    # Update the distance if a shorter path is found
                    if new_distance < distances[neighbor]:
                        distances[neighbor] = new_distance
                        previous_nodes[neighbor] = current_node
                        queue.append((new_distance, neighbor))

    def rib_query_next_multicast_hops(self, start, multicast_group_name):
        # If the multicast group is not in the RIB, forward to the parent router
        if not multicast_group_name in self.rib_multicast_groups:
            if not self.parent_router:
                print(f"Could not find multicast group '{multicast_group_name}'!")
                return

            message = Message(
                content=multicast_group_name,
                type=MessageTypes.RIB_QUERY_NEXT_MULTICAST_HOPS,
            )
            return self.send_message(start, self.parent_router, message)

        multicast_group = self.rib_multicast_groups[multicast_group_name]
        next_hops = []

        # Check for next hops inside the trust domain
        if multicast_group["is_member"]:
            internal_next_hops = [
                n2 if n1 == start else n1
                for n1, n2, _ in multicast_group["internal_edges"]
                if start in (n1, n2)
            ]

            next_hops.extend(internal_next_hops)

        # If we're at a router, also check for next hops outside the trust domain
        if isinstance(start, Router):
            # If this router is the LCA, compute external hops
            if multicast_group["lca"] == self:
                external_next_hops = [
                    n2 if n1 == start else n1
                    for n1, n2, _ in multicast_group["external_edges"]
                    if start in (n1, n2)
                ]

                next_hops.extend(external_next_hops)

            # Else, forward the query to the parent router
            elif self.parent_router:
                message = Message(
                    content=multicast_group_name,
                    type=MessageTypes.RIB_QUERY_NEXT_MULTICAST_HOPS,
                )
                external_next_hops = self.send_message(
                    start, self.parent_router, message
                )

                next_hops.extend(external_next_hops)

        return next_hops

    # Returns the full shortest path (a list of edges) from 'start' to any of the nodes in 'destinations'
    def dijkstra_path_to_any_node(self, start, destinations):
        # Initialize distance and previous node dictionaries
        distances = {node: float("infinity") for node in self.rib_nodes}
        previous_nodes = {node: None for node in self.rib_nodes}

        # Initialize the priority list
        queue = [(0, start)]
        distances[start] = 0

        while queue:
            # Find and remove the node with the smallest distance
            current_distance, current_node = min(queue, key=lambda x: x[0])
            queue.remove((current_distance, current_node))

            # If a destination is reached, backtrack to find the full path as edges
            if current_node in destinations:
                return backtrack_full_path(
                    start, current_node, previous_nodes, self.rib_edges
                )

            # Iterate over neighbors of the current node
            for edge in self.rib_edges:
                if current_node in edge:
                    neighbor = edge[0] if current_node == edge[1] else edge[1]
                    length = edge[2]
                    new_distance = current_distance + length

                    # Update the distance if a shorter path is found
                    if new_distance < distances[neighbor]:
                        distances[neighbor] = new_distance
                        previous_nodes[neighbor] = current_node
                        queue.append((new_distance, neighbor))

        return None  # Path not found to any destination

    def rib_add_link(self, node1, node2, link_cost):
        self.rib_nodes.add(node1)
        self.rib_nodes.add(node2)
        self.rib_edges.add((node1, node2, link_cost))

        if self.parent_router:
            # If link crosses trust domain boundary, propagate up the tree
            if node1.get_trust_domain_router() != node2.get_trust_domain_router():
                message = Message(
                    content=(node1, node2, link_cost), type=MessageTypes.RIB_ADD_LINK
                )
                self.send_message(self, self.parent_router, message)

            # Else, propagate node ownership up the tree
            else:
                message = Message(
                    content=(node1.parent_router, node1),
                    type=MessageTypes.RIB_ADD_OWNERSHIP,
                )
                self.send_message(self, self.parent_router, message)

                message = Message(
                    content=(node2.parent_router, node2),
                    type=MessageTypes.RIB_ADD_OWNERSHIP,
                )
                self.send_message(self, self.parent_router, message)

    def rib_add_ownership(self, router, node):
        if self != router:
            if not router in self.rib_child_router_ownerships:
                self.rib_child_router_ownerships[router] = set()
            self.rib_child_router_ownerships[router].add(node)

        # Propagate ownership up the tree
        if self.parent_router:
            message = Message(
                content=(router, node), type=MessageTypes.RIB_ADD_OWNERSHIP
            )
            self.send_message(self, self.parent_router, message)

    def rib_add_multicast_group(
        self, creator, group_name, lowest_common_ancestor, owner
    ):
        self.rib_multicast_groups[group_name] = {
            "lca": lowest_common_ancestor,
            "is_member": False,
            "owner": owner,
        }

        if lowest_common_ancestor == self:
            self.rib_multicast_groups[group_name]["external_members"] = set()
            self.rib_multicast_groups[group_name]["external_nodes"] = set()
            self.rib_multicast_groups[group_name]["external_edges"] = set()

        # Propagate group creation up the tree
        if self.parent_router:
            message = Message(
                content=(group_name, lowest_common_ancestor, owner),
                type=MessageTypes.ADD_MULTICAST_GROUP,
            )
            self.send_message(creator, self.parent_router, message)

    def rib_router_join_multicast_group(self, router, group_name):
        # If the RIB doesn't know about the group, create it
        if not group_name in self.rib_multicast_groups:
            if not self.parent_router:
                print(f"Could not find multicast group '{group_name}'!")
                return

            self.rib_multicast_groups[group_name] = {
                "internal_members": set(),
                "internal_nodes": set([self]),
                "internal_edges": set(),
                "lca": None,  # This router doesn't need to know the LCA router
                "is_member": True,
            }
        elif not self.rib_multicast_groups[group_name]["is_member"]:
            multicast_group = self.rib_multicast_groups[group_name]
            multicast_group["is_member"] = True
            multicast_group["internal_members"] = set()
            multicast_group["internal_nodes"] = set([self])
            multicast_group["internal_edges"] = set()

        # If the current LCA is a descendant router, set this router as the new LCA
        # TODO: This is kinda cheating, but it works
        lca_is_descendant = False
        tmp_router = self.rib_multicast_groups[group_name]["lca"]
        while tmp_router:
            tmp_router = tmp_router.parent_router
            if tmp_router == self:
                lca_is_descendant = True
                break
        if lca_is_descendant:
            # Request old LCA to move the tree to this router
            message = Message(
                content=group_name, type=MessageTypes.MULTICAST_GROUP_TRANSFER_LCA
            )
            external_members, external_nodes, external_edges = self.send_message(
                self, self.rib_multicast_groups[group_name]["lca"], message
            )

            self.rib_multicast_groups[group_name]["external_members"] = external_members
            self.rib_multicast_groups[group_name]["external_nodes"] = external_nodes
            self.rib_multicast_groups[group_name]["external_edges"] = external_edges

            # Add previous LCA as a node in the multicast tree and compute path
            previous_lca = self.rib_multicast_groups[group_name]["lca"]
            if len(self.rib_multicast_groups[group_name]["external_nodes"]) > 0:
                nodes, edges = self.dijkstra_path_to_any_node(
                    previous_lca,
                    self.rib_multicast_groups[group_name]["external_nodes"],
                )
                self.rib_multicast_groups[group_name]["external_nodes"].update(nodes)
                self.rib_multicast_groups[group_name]["external_edges"].update(edges)

            self.rib_multicast_groups[group_name]["external_nodes"].add(previous_lca)
            self.rib_multicast_groups[group_name]["lca"] = self

            # Let all other routers know that this router is the new LCA
            # TODO: This is kinda cheating, but it works
            for r in self.rib_nodes:
                if isinstance(r, Router) and group_name in r.rib_multicast_groups:
                    r.rib_multicast_groups[group_name]["lca"] = self

        # If this router is the LCA, add the querying router to the multicast group and compute path
        if self.rib_multicast_groups[group_name]["lca"] == self:
            # Find edges that connects the router to the multicast tree
            if len(self.rib_multicast_groups[group_name]["external_nodes"]) > 0:
                nodes, edges = self.dijkstra_path_to_any_node(
                    router, self.rib_multicast_groups[group_name]["external_nodes"]
                )

                # Add connecting nodes and edges to the multicast tree
                self.rib_multicast_groups[group_name]["external_nodes"].update(nodes)
                self.rib_multicast_groups[group_name]["external_edges"].update(edges)

            # Add router to the multicast group
            self.rib_multicast_groups[group_name]["external_nodes"].add(router)
            self.rib_multicast_groups[group_name]["external_members"].add(router)

            # Add itself to the internal multicast tree
            if len(self.rib_multicast_groups[group_name]["internal_nodes"]) > 0:
                nodes, edges = self.dijkstra_path_to_any_node(
                    self, self.rib_multicast_groups[group_name]["internal_nodes"]
                )
                self.rib_multicast_groups[group_name]["internal_nodes"].update(nodes)
                self.rib_multicast_groups[group_name]["internal_edges"].update(edges)
            self.rib_multicast_groups[group_name]["internal_nodes"].add(self)

            return self.rib_multicast_groups[group_name]["owner"]

        # Else, forward the join request to the parent router
        else:
            global TREE_BUILD_WEIGHT  # TODO: FIGURE OUT DIJKSTRA OVERHEAD
            TREE_BUILD_WEIGHT += 100
            message = Message(
                content=group_name,
                type=MessageTypes.ROUTER_JOIN_MULTICAST_GROUP,
            )
            owner = self.send_message(router, self.parent_router, message)
            self.rib_multicast_groups[group_name]["owner"] = owner

            return owner

    def rib_client_join_multicast_group(self, client, group_name):
        # Add the client's trust domain router to the external multicast group
        owner = self.rib_router_join_multicast_group(
            self.get_trust_domain_router(),
            group_name,
        )

        # Find edges that connects the client to the internal multicast tree
        if len(self.rib_multicast_groups[group_name]["internal_nodes"]) > 0:
            nodes, edges = self.dijkstra_path_to_any_node(
                client, self.rib_multicast_groups[group_name]["internal_nodes"]
            )

            # Add connecting nodes and edges to the multicast tree
            self.rib_multicast_groups[group_name]["internal_nodes"].update(nodes)
            self.rib_multicast_groups[group_name]["internal_edges"].update(edges)

        # Add client to the internal multicast group
        self.rib_multicast_groups[group_name]["internal_nodes"].add(client)
        self.rib_multicast_groups[group_name]["internal_members"].add(client)

        # Return the owner of the multicast group
        return owner

    def rib_multicast_group_transfer_lca(self, new_lca_router, group_name):
        external_members = self.rib_multicast_groups[group_name]["external_members"]
        external_nodes = self.rib_multicast_groups[group_name]["external_nodes"]
        external_edges = self.rib_multicast_groups[group_name]["external_edges"]

        # Remove external tree from the stored multicast group
        del self.rib_multicast_groups[group_name]["external_members"]
        del self.rib_multicast_groups[group_name]["external_nodes"]
        del self.rib_multicast_groups[group_name]["external_edges"]

        # Add itself to the internal multicast tree
        nodes, edges = self.dijkstra_path_to_any_node(
            self, self.rib_multicast_groups[group_name]["internal_nodes"]
        )
        self.rib_multicast_groups[group_name]["internal_nodes"].update(nodes)
        self.rib_multicast_groups[group_name]["internal_edges"].update(edges)
        self.rib_multicast_groups[group_name]["internal_nodes"].add(self)

        # Update the LCA router
        self.rib_multicast_groups[group_name]["lca"] = new_lca_router

        # Send the routers and router edges back to the new LCA router
        return external_members, external_nodes, external_edges


# Helper function
def backtrack_first_hop(start, destination, previous_nodes):
    # Backtrack from destination to start, return the first hop
    node = destination
    while previous_nodes[node] != start:
        node = previous_nodes[node]

        # Handle case where no path exists
        if node is None:
            return None

    return node


# Helper function
def backtrack_full_path(start, destination, previous_nodes, edges):
    path_edges = []
    path_nodes = {start, destination}
    node = destination

    while node != start:
        prev_node = previous_nodes[node]
        if prev_node is None:
            return None  # In case the path is broken

        # Add the node to the path nodes set
        path_nodes.add(prev_node)

        # Find the edge that connects the current node and the previous node
        for edge in edges:
            if (prev_node in edge) and (node in edge):
                path_edges.append(edge)
                break

        node = prev_node

    return (
        path_nodes,
        path_edges[::-1],
    )  # Return the path as nodes and edges in the correct order from start to destination


def main():
    # Enable to print every message received at any node. Disable to only print messages received at clients.
    global DEBUG

    total_root_messages = 0

    seed = 0
    counter = 0
    COUNT = 1000
    while counter < COUNT:
        random.seed(seed)
        try:
            routerRoot = Router("RouterRoot", None)

            first_layer_routers = []
            for i in range(3):
                curr_router = Router(
                    f"FirstLayerRouter{i + 1}", parent_router=routerRoot
                )
                curr_router.add_neighbor(routerRoot)
                first_layer_routers.append(curr_router)

            second_layer_routers = []
            for flr in first_layer_routers:
                for i in range(4):
                    curr_router = Router(f"SecondLayerRouter{i + 1}", parent_router=flr)
                    curr_router.add_neighbor(flr)
                    second_layer_routers.append(curr_router)

            third_layer_routers = []
            for slr in second_layer_routers:
                for i in range(7):
                    curr_router = Router(f"ThirdLayerRouter{i + 1}", parent_router=slr)
                    curr_router.add_neighbor(slr)
                    third_layer_routers.append(curr_router)

            clients = []

            def add_clients(base_router, idx):
                switch1 = Switch(f"FLswitch1A_{idx}", parent_router=base_router)
                switch1.add_neighbor(base_router)
                client1A = Client(f"FLclient1A_{idx}", switch1)
                client2A = Client(f"FLclient2A_{idx}", switch1)

                switch2 = Switch(f"FLswitch2A_{idx}", parent_router=base_router)
                switch2.add_neighbor(base_router)
                client3A = Client(f"FLclient3A_{idx}", switch2)
                client4A = Client(f"FLclient4A_{idx}", switch2)

                switch3 = Switch(f"FLswitch3A_{idx}", parent_router=base_router)
                switch3.add_neighbor(base_router)
                client5A = Client(f"FLclient5A_{idx}", switch3)
                client6A = Client(f"FLclient6A_{idx}", switch3)

                switch4 = Switch(f"FLswitch4A_{idx}", parent_router=base_router)
                switch4.add_neighbor(base_router)
                client7A = Client(f"FLclient7A_{idx}", switch4)
                client8A = Client(f"FLclient8A_{idx}", switch4)

                switch5 = Switch(f"FLswitch5A_{idx}", parent_router=base_router)
                switch5.add_neighbor(base_router)
                client9A = Client(f"FLclient9A_{idx}", switch5)
                client10A = Client(f"FLclient10A_{idx}", switch5)

                clients.append(client1A)
                clients.append(client2A)
                clients.append(client3A)
                clients.append(client4A)
                clients.append(client5A)
                clients.append(client6A)
                clients.append(client7A)
                clients.append(client8A)
                clients.append(client9A)
                clients.append(client10A)

            curr_idx = 0

            add_clients(routerRoot, curr_idx)
            curr_idx += 1

            for flr in first_layer_routers:
                add_clients(flr, curr_idx)
                curr_idx += 1

            for slr in second_layer_routers:
                add_clients(slr, curr_idx)
                curr_idx += 1

            for tlr in third_layer_routers:
                add_clients(tlr, curr_idx)
                curr_idx += 1

            # print(
            #     len(first_layer_routers),
            #     len(second_layer_routers),
            #     len(third_layer_routers),
            #     len(clients),
            # )

            # Set up random links between routers in the network. For any pair of routers, there is a 25% chance that they are connected.
            PROBABILITY_OF_LINK = 0.25
            for i in range(len(first_layer_routers)):
                for j in range(i + 1, len(first_layer_routers)):
                    if random.random() < PROBABILITY_OF_LINK:
                        first_layer_routers[i].add_neighbor(first_layer_routers[j])

            for i in range(len(second_layer_routers)):
                for j in range(i + 1, len(second_layer_routers)):
                    if random.random() < PROBABILITY_OF_LINK:
                        second_layer_routers[i].add_neighbor(second_layer_routers[j])

            for i in range(len(third_layer_routers)):
                for j in range(i + 1, len(third_layer_routers)):
                    if random.random() < PROBABILITY_OF_LINK:
                        third_layer_routers[i].add_neighbor(third_layer_routers[j])

            # Reset total edge cost after setting up the network
            global ROUTER_ROOT_MESSAGES
            ROUTER_ROOT_MESSAGES = 0

            # Create 10 multicast groups with 10 random clients each
            for i in range(10):
                recipients = random.sample(clients, 10)
                recipients[0].create_multicast_group(f"group{i+1}")

                for rec in recipients[1:]:
                    rec.join_multicast_group(f"group{i+1}")

                # Send 10 multicast messages
                for _ in range(10):
                    recipients[0].send_multicast_message(
                        recipients[0],
                        f"group{i+1}",
                        Message(f"Hello from group{i+1}!", MessageTypes.PING),
                    )

            recipients = random.sample(clients, 10)

            for rec in recipients:
                rec.join_multicast_group("group1")

            print(ROUTER_ROOT_MESSAGES, end=", ")
            total_root_messages += ROUTER_ROOT_MESSAGES

            counter += 1
            seed += 1
        except KeyboardInterrupt:
            print("stopped")
            break
        except:
            seed += 1

    print("")
    print(f"Average total root messages: {total_root_messages / COUNT}")


main()
