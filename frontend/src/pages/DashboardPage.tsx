import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Users, FileText, Briefcase, TrendingUp } from "lucide-react";

const stats = [
    {
        title: "Total Candidates",
        value: "1,234",
        description: "+20.1% from last month",
        icon: Users,
        color: "text-blue-600",
    },
    {
        title: "Active Applications",
        value: "45",
        description: "+180.1% from last month",
        icon: FileText,
        color: "text-purple-600",
    },
    {
        title: "Open Positions",
        value: "12",
        description: "+19% from last month",
        icon: Briefcase,
        color: "text-green-600",
    },
    {
        title: "Hire Rate",
        value: "24%",
        description: "+4% from last month",
        icon: TrendingUp,
        color: "text-orange-600",
    },
];

export default function DashboardPage() {
    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
                <p className="text-muted-foreground">
                    Overview of your recruitment pipeline and activities.
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {stats.map((stat) => (
                    <Card key={stat.title}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">
                                {stat.title}
                            </CardTitle>
                            <stat.icon className={`h-4 w-4 ${stat.color}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stat.value}</div>
                            <p className="text-xs text-muted-foreground">
                                {stat.description}
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Recent Applications</CardTitle>
                        <CardDescription>
                            You made 265 sales this month.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-muted-foreground">
                            [Placeholder for Chart or Table]
                        </p>
                    </CardContent>
                </Card>
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Recent Activity</CardTitle>
                        <CardDescription>
                            Latest actions across the system.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-muted-foreground">
                            [Placeholder for Activity Feed]
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
