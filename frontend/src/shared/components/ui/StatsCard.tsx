import { Card, CardContent } from "../../../components/ui/Card";
import { cn } from "../../utils/cn";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface StatsCardProps {
    title: string;
    value: string | number;
    icon: LucideIcon;
    trend?: {
        value: number;
        isPositive: boolean;
    };
    description?: string;
    className?: string;
}

export function StatsCard({ title, value, icon: Icon, trend, description, className }: StatsCardProps) {
    return (
        <Card className={cn("overflow-hidden", className)}>
            <CardContent className="p-6">
                <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-gray-500">{title}</p>
                    <Icon className="h-4 w-4 text-gray-500" />
                </div>
                <div className="flex flex-col gap-1">
                    <div className="text-2xl font-bold text-gray-900">{value}</div>
                    {(trend || description) && (
                        <div className="flex items-center text-xs text-gray-500 gap-2">
                            {trend && (
                                <span className={cn(
                                    "flex items-center gap-0.5 font-medium",
                                    trend.isPositive ? "text-green-600" : "text-red-600"
                                )}>
                                    {trend.isPositive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                                    {Math.abs(trend.value)}%
                                </span>
                            )}
                            {description && <span>{description}</span>}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
