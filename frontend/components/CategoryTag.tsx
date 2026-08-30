import { EmailCategory } from "@/lib/types";

const CATEGORY_COLORS: Record<EmailCategory, string> = {
  recruiter: "text-category-recruiter border-category-recruiter/30 bg-category-recruiter/10",
  internship: "text-category-internship border-category-internship/30 bg-category-internship/10",
  meeting: "text-category-meeting border-category-meeting/30 bg-category-meeting/10",
  professor: "text-category-professor border-category-professor/30 bg-category-professor/10",
  conference: "text-category-conference border-category-conference/30 bg-category-conference/10",
  reminder: "text-category-reminder border-category-reminder/30 bg-category-reminder/10",
  personal: "text-category-personal border-category-personal/30 bg-category-personal/10",
  newsletter: "text-category-newsletter border-category-newsletter/30 bg-category-newsletter/10",
  promotion: "text-category-promotion border-category-promotion/30 bg-category-promotion/10",
  unknown: "text-category-unknown border-category-unknown/30 bg-category-unknown/10",
};

export function CategoryTag({ category }: { category: EmailCategory }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide ${CATEGORY_COLORS[category]}`}
    >
      {category}
    </span>
  );
}