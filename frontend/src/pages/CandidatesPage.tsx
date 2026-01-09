import { useState } from "react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/Card";
import { Plus, Search, MoreHorizontal, Mail, Phone, MapPin } from "lucide-react";

interface Candidate {
    id: string;
    name: string;
    role: string;
    email: string;
    phone: string;
    location: string;
    status: "New" | "Interviewing" | "Offer" | "Hired";
    appliedDate: string;
}

const mockCandidates: Candidate[] = [
    {
        id: "1",
        name: "Alex Johnson",
        role: "Senior Frontend Engineer",
        email: "alex.j@example.com",
        phone: "+1 (555) 123-4567",
        location: "New York, NY",
        status: "Interviewing",
        appliedDate: "2024-03-10",
    },
    {
        id: "2",
        name: "Sarah Williams",
        role: "Product Manager",
        email: "sarah.w@example.com",
        phone: "+1 (555) 987-6543",
        location: "San Francisco, CA",
        status: "New",
        appliedDate: "2024-03-12",
    },
    {
        id: "3",
        name: "Michael Chen",
        role: "Backend Developer",
        email: "m.chen@example.com",
        phone: "+1 (555) 456-7890",
        location: "Austin, TX",
        status: "Offer",
        appliedDate: "2024-03-05",
    },
];

export default function CandidatesPage() {
    const [searchTerm, setSearchTerm] = useState("");

    const filteredCandidates = mockCandidates.filter(c =>
        c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.role.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Candidates</h2>
                    <p className="text-muted-foreground">
                        Manage your candidate pool and track applications.
                    </p>
                </div>
                <Button>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Candidate
                </Button>
            </div>

            <div className="flex items-center space-x-2">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search candidates..."
                        className="pl-8"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                {/* Filter buttons could go here */}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredCandidates.map((candidate) => (
                    <Card key={candidate.id} className="overflow-hidden transition-all hover:shadow-md">
                        <CardHeader className="pb-4">
                            <div className="flex justify-between items-start">
                                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-xl font-bold text-primary">
                                    {candidate.name.charAt(0)}
                                </div>
                                <Button variant="ghost" size="icon" className="-mr-2 -mt-2">
                                    <MoreHorizontal className="h-4 w-4" />
                                </Button>
                            </div>
                            <CardTitle className="mt-4">{candidate.name}</CardTitle>
                            <p className="text-sm font-medium text-muted-foreground">{candidate.role}</p>
                        </CardHeader>
                        <CardContent className="space-y-3 text-sm">
                            <div className="flex items-center text-muted-foreground">
                                <Mail className="mr-2 h-4 w-4" />
                                {candidate.email}
                            </div>
                            <div className="flex items-center text-muted-foreground">
                                <Phone className="mr-2 h-4 w-4" />
                                {candidate.phone}
                            </div>
                            <div className="flex items-center text-muted-foreground">
                                <MapPin className="mr-2 h-4 w-4" />
                                {candidate.location}
                            </div>
                            <div className="pt-2 flex justify-between items-center">
                                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium 
                  ${candidate.status === 'New' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300' :
                                        candidate.status === 'Interviewing' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300' :
                                            candidate.status === 'Offer' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
                                                'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'}`}>
                                    {candidate.status}
                                </span>
                                <span className="text-xs text-muted-foreground">Applied {candidate.appliedDate}</span>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
