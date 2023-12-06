from enum import Enum

# Enable to print every message received at any node. Disable to only print messages received at clients.
DEBUG = False


class MessageTypes(Enum):
    PING = 0
    RIB_ADD_LINK = 1
    RIB_ADD_OWNERSHIP = 2
    RIB_QUERY_NEXT_HOP = 3
    MULTICAST_CREATE_GROUP = 4
    MULTICAST_JOIN_GROUP = 5
    RIB_QUERY_NEXT_MULTICAST_HOPS = 6
    MULTICAST_NOTIFY_NEW_MEMBER = 7


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
        return next_hop.receive_message(source, destination, message)

    def receive_message(self, source, destination, message):
        if self == destination:
            # Handle message
            return self.handle_message(source, message)
        else:
            # if message.type == MessageTypes.PING:
            #     print(
            #         f"[{self}] Forwarding message to {self.get_next_hop(destination)}"
            #     )

            # Forward to next hop
            return self.send_message(source, destination, message)

    def send_multicast_message(self, source, multicast_group, message, visited=set()):
        next_hops = self.get_next_multicast_hops(multicast_group)
        updated_visited = visited.copy()
        updated_visited.add(self)
        return [
            next_hop.receive_multicast_message(
                source, multicast_group, message, updated_visited
            )
            for next_hop in next_hops
            if next_hop not in visited
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
        print(f"[{self}] Received message from {source}: {message}")

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Switch(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)


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

    def handle_message(self, source, message):
        super().handle_message(source, message)

    def create_multicast_group(self, group_name):
        message = Message(content=group_name, type=MessageTypes.MULTICAST_CREATE_GROUP)
        self.send_message(self, self.parent_router, message)
        self.multicast_groups.add(group_name)

    def join_multicast_group(self, group_name):
        message = Message(content=group_name, type=MessageTypes.MULTICAST_JOIN_GROUP)
        response = self.send_message(self, self.parent_router, message)
        self.multicast_groups.add(group_name)


class Router(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)

        # Everything below here is the RIB (lives inside the router)
        self.rib_nodes = set()
        self.rib_edges = set()
        self.rib_child_router_ownerships = {}
        self.rib_multicast_groups = {}

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

        elif message.type == MessageTypes.MULTICAST_CREATE_GROUP:
            group_name = message.content
            self.rib_create_multicast_group(source, group_name)

        elif message.type == MessageTypes.MULTICAST_JOIN_GROUP:
            group_name = message.content
            self.rib_join_multicast_group(source, group_name)

        elif message.type == MessageTypes.MULTICAST_NOTIFY_NEW_MEMBER:
            group_name = message.content
            self.rib_notify_new_multicast_member(source, group_name)

    def rib_query_next_hop(self, start, destination):
        # Try to route with local RIB
        result = self.dijkstra_path_to_single_node(start, destination)
        if result:
            return result

        # Forward to parent RIB
        if self.parent_router:
            message = Message(
                content=(start, destination), type=MessageTypes.RIB_QUERY_NEXT_HOP
            )
            return self.send_message(self, self.parent_router, message)

        return None  # Path not found

        # # If the destination is in the same trust domain, use Dijkstra's algorithm within the domain
        # if destination.parent_router == self:
        #     next_hop, distance = self.dijkstra_path_to_single_node(start, destination)
        #     return next_hop, distance

        # # If the destination is not in the same trust domain, first route to the sender's trust domain router
        # # Then, route to the destination's trust domain router
        # else:
        #     # If the destination is a client, route to the client's trust domain's router
        #     destination = (
        #         destination
        #         if isinstance(destination, Router)
        #         else destination.parent_router
        #     )

        #     # Try to route with local RIB
        #     result = self.dijkstra_path_to_single_node(start, destination)
        #     if result:
        #         return result

        #     if not isinstance(start, Router) and start.parent_router == self:
        #         # Route to the sender's trust domain router
        #         next_hop, distance = self.dijkstra_path_to_single_node(
        #             start, start.parent_router
        #         )
        #         return next_hop, distance

        #     # Else ask the parent RIB for the next hop to the destination's trust domain router
        #     if self.parent_router:
        #         message = Message(
        #             content=(start, destination),
        #             type=MessageTypes["RIB_QUERY_NEXT_HOP"],
        #         )

        #         return self.send_message(self, self.parent_router, message)

        # return None  # Path not found

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
        if not multicast_group_name in self.rib_multicast_groups:
            print(f"[{self}] Could not find multicast group '{multicast_group_name}'!")
            return

        multicast_group = self.rib_multicast_groups[multicast_group_name]

        next_hops = [
            n2 if n1 == start else n1
            for n1, n2, _ in multicast_group["edges"]
            if start in (n1, n2)
        ]

        # Also check the parent RIB for potenital links outside the domain
        if self.parent_router:
            message = Message(
                content=multicast_group_name,
                type=MessageTypes.RIB_QUERY_NEXT_MULTICAST_HOPS,
            )
            external_next_hops = self.send_message(
                start.get_trust_domain_router(), self.parent_router, message
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
            # Propagate link up the tree
            message = Message(
                content=(node1, node2, link_cost), type=MessageTypes.RIB_ADD_LINK
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
                content=(node.parent_router, node), type=MessageTypes.RIB_ADD_OWNERSHIP
            )
            self.send_message(self, self.parent_router, message)

    def rib_create_multicast_group(self, creator, group_name):
        self.rib_multicast_groups[group_name] = {
            "members": set([creator]),
            "nodes": set([creator]),
            "edges": set(),
        }

        # Propagate group creation up the tree
        if self.parent_router:
            message = Message(
                content=group_name, type=MessageTypes.MULTICAST_CREATE_GROUP
            )
            self.send_message(
                creator.get_trust_domain_router(), self.parent_router, message
            )

    def rib_join_multicast_group(self, node, group_name):
        # If this RIB doesn't know about the multicast group, save the group and forward to parent router
        if not group_name in self.rib_multicast_groups:
            if not self.parent_router:
                print(f"Could not find multicast group '{group_name}'!")
                return

            self.rib_multicast_groups[group_name] = {
                "members": set(),
                "nodes": set(),
                "edges": set(),
            }

            # Router adds itself to the multicast tree
            self.rib_multicast_groups[group_name]["nodes"].add(self)

            message = Message(
                content=group_name, type=MessageTypes.MULTICAST_JOIN_GROUP
            )
            self.send_message(
                node.get_trust_domain_router(), self.parent_router, message
            )

        if self.rib_multicast_groups[group_name]["nodes"]:
            # Find edges that connects the node to the multicast tree
            nodes, edges = self.dijkstra_path_to_any_node(
                node, self.rib_multicast_groups[group_name]["nodes"]
            )

            # Add nodes and edges to the multicast tree
            self.rib_multicast_groups[group_name]["nodes"].update(nodes)
            self.rib_multicast_groups[group_name]["edges"].update(edges)

        self.rib_multicast_groups[group_name]["nodes"].add(node)
        self.rib_multicast_groups[group_name]["members"].add(node)

        # Let other routers in the group know about the new member
        for member in self.rib_multicast_groups[group_name]["members"]:
            if isinstance(member, Router) and member != node.get_trust_domain_router():
                message = Message(
                    content=group_name, type=MessageTypes.MULTICAST_NOTIFY_NEW_MEMBER
                )
                self.send_message(node.get_trust_domain_router(), member, message)

    def rib_notify_new_multicast_member(self, node, group_name):
        next_hop, distance = self.rib_query_next_hop(self, node)

        if group_name not in self.multicast_routing_table:
            self.multicast_routing_table[group_name] = set()

        self.multicast_routing_table[group_name].add(next_hop)


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

    # Trust domain 1
    router1 = Router("router1", None)
    switch1A = Switch("switch1A", router1)
    switch1A.add_neighbor(router1)
    switch1B = Switch("switch1B", router1)
    switch1B.add_neighbor(router1)

    # Trust domain 2A
    router2A = Router("router2A", router1)
    router2A.add_neighbor(switch1A)
    switch2A = Switch("switch2A", router2A)
    switch2A.add_neighbor(router2A)
    client2A = Client("client2A", switch2A)

    # Trust domain 2B
    router2B = Router("router2B", router1)
    router2B.add_neighbor(switch1B)
    switch2B = Switch("switch2B", router2B)
    switch2B.add_neighbor(router2B)

    # Trust domain 3A
    router3A = Router("router3A", router2A)
    router3A.add_neighbor(switch2A)
    switch3A = Switch("switch3A", router3A)
    switch3A.add_neighbor(router3A)
    client3A = Client("client3A", switch3A)

    # Trust domain 3B
    router3B = Router("router3B", router2B)
    router3B.add_neighbor(switch2B)
    switch3B = Switch("switch3B", router3B)
    switch3B.add_neighbor(router3B)
    client3B = Client("client3B", switch3B)

    router3A.add_neighbor(router3B, 1)

    # Send messages
    # client3A.send_message(
    #     client3A, client3B, Message("Hello, world!", MessageTypes.PING)
    # )

    client3A.create_multicast_group("group1")
    client2A.join_multicast_group("group1")
    client3B.join_multicast_group("group1")
    client3A.send_multicast_message(
        client3A, "group1", Message("Hello, multicast world!", MessageTypes.PING)
    )

    print("done")


main()
