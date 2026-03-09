declare module 'react-resizable-panels' {
    import * as React from 'react';

    export interface PanelProps {
        children?: React.ReactNode;
        className?: string;
        collapsible?: boolean;
        defaultSize?: number;
        id?: string;
        maxSize?: number;
        minSize?: number;
        onCollapse?: () => void;
        onExpand?: () => void;
        onResize?: (size: number) => void;
        order?: number;
        style?: React.CSSProperties;
        tagName?: React.ElementType;
    }

    export const Panel: React.FC<PanelProps>;

    export interface GroupProps {
        autoSaveId?: string;
        children?: React.ReactNode;
        className?: string;
        direction: 'horizontal' | 'vertical';
        id?: string;
        onLayout?: (sizes: number[]) => void;
        storage?: any;
        style?: React.CSSProperties;
        tagName?: React.ElementType;
    }

    export const Group: React.FC<GroupProps>;

    export interface SeparatorProps {
        className?: string;
        disabled?: boolean;
        id?: string;
        style?: React.CSSProperties;
        tagName?: React.ElementType;
        children?: React.ReactNode;
    }

    export const Separator: React.FC<SeparatorProps>;
}
